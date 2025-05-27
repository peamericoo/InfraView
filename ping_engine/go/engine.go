package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"sync"
	"time"

	"github.com/go-ping/ping"
	pb "github.com/infra/pingservice/infraview/pingservice"
	"google.golang.org/grpc"
)

////////////////////////////////////////////////////////////////////////////////
// TIPOS E ESTRUTURA DE DADOS
////////////////////////////////////////////////////////////////////////////////

type serverStatus struct {
	cancel context.CancelFunc
	paused bool
}

// PingServer implementa pb.PingServiceServer
type PingServer struct {
	pb.UnimplementedPingServiceServer

	mu           sync.RWMutex
	servers      map[string]serverStatus
	statusCh     map[string]chan *pb.StatusUpdate
	aggregatorCh chan *pb.StatusUpdate // fan-in global para o StreamStatus
}

////////////////////////////////////////////////////////////////////////////////
// CONSTRUTOR
////////////////////////////////////////////////////////////////////////////////

func NewPingServer() *PingServer {
	return &PingServer{
		servers:      make(map[string]serverStatus),
		statusCh:     make(map[string]chan *pb.StatusUpdate),
		aggregatorCh: make(chan *pb.StatusUpdate, 1000),
	}
}

////////////////////////////////////////////////////////////////////////////////
// HELPERS
////////////////////////////////////////////////////////////////////////////////

func (ps *PingServer) isPaused(ip string) bool {
	ps.mu.RLock()
	defer ps.mu.RUnlock()
	st, ok := ps.servers[ip]
	return ok && st.paused
}

// copia cada update de um canal específico para o fan-in global
func (ps *PingServer) forwardLoop(src <-chan *pb.StatusUpdate) {
	for upd := range src {
		select {
		case ps.aggregatorCh <- upd:
		default: // não bloquear a engine se o consumidor estiver lento
			log.Printf("aggregator cheio — descartando update de %s", upd.GetIp())
		}
	}
}

////////////////////////////////////////////////////////////////////////////////
// MÉTODOS gRPC
////////////////////////////////////////////////////////////////////////////////

// AddServer cria pingLoop, canal bufferizado e forwardLoop por IP
func (ps *PingServer) AddServer(ctx context.Context, req *pb.AddRequest) (*pb.Ack, error) {
	ip := req.GetIp()

	ps.mu.Lock()
	if _, exists := ps.servers[ip]; exists {
		ps.mu.Unlock()
		return &pb.Ack{Success: false, Message: "Already exists"}, nil
	}

	ctxPing, cancel := context.WithCancel(context.Background())
	ps.servers[ip] = serverStatus{cancel: cancel, paused: false}

	ch := make(chan *pb.StatusUpdate, 100)
	ps.statusCh[ip] = ch
	ps.mu.Unlock()

	go ps.forwardLoop(ch)
	go ps.pingLoop(ctxPing, ip, ch)

	return &pb.Ack{Success: true, Message: "Added"}, nil
}

func (ps *PingServer) RemoveServer(ctx context.Context, req *pb.RemoveRequest) (*pb.Ack, error) {
	ip := req.GetIp()

	ps.mu.Lock()
	status, exists := ps.servers[ip]
	if !exists {
		ps.mu.Unlock()
		return &pb.Ack{Success: false, Message: "Not found"}, nil
	}

	status.cancel() // sinaliza pingLoop para encerrar e fechar canal
	delete(ps.servers, ip)
	delete(ps.statusCh, ip)
	ps.mu.Unlock()

	return &pb.Ack{Success: true, Message: "Removed"}, nil
}

func (ps *PingServer) PauseServer(ctx context.Context, req *pb.PauseRequest) (*pb.Ack, error) {
	ip := req.GetIp()

	ps.mu.Lock()
	status, exists := ps.servers[ip]
	if !exists {
		ps.mu.Unlock()
		return &pb.Ack{Success: false, Message: "Not found"}, nil
	}

	status.paused = true
	ps.servers[ip] = status
	ps.mu.Unlock()

	return &pb.Ack{Success: true, Message: "Paused"}, nil
}

func (ps *PingServer) ResumeServer(ctx context.Context, req *pb.ResumeRequest) (*pb.Ack, error) {
	ip := req.GetIp()

	ps.mu.Lock()
	status, exists := ps.servers[ip]
	if !exists {
		ps.mu.Unlock()
		return &pb.Ack{Success: false, Message: "Not found"}, nil
	}

	status.paused = false
	ps.servers[ip] = status
	ps.mu.Unlock()

	return &pb.Ack{Success: true, Message: "Resumed"}, nil
}

// StreamStatus agora consome só o fan-in global, sem varrer todos os canais
func (ps *PingServer) StreamStatus(_ *pb.StatusRequest, stream pb.PingService_StreamStatusServer) error {
	for {
		select {
		case <-stream.Context().Done():
			return nil
		case upd := <-ps.aggregatorCh:
			if err := stream.Send(upd); err != nil {
				return err
			}
		}
	}
}

////////////////////////////////////////////////////////////////////////////////
// LOOP DE PING POR IP
////////////////////////////////////////////////////////////////////////////////

const pingInterval = 2 * time.Second

func (ps *PingServer) pingLoop(ctx context.Context, ip string, statusChan chan<- *pb.StatusUpdate) {
	ticker := time.NewTicker(pingInterval)
	defer ticker.Stop()
	defer close(statusChan) // garante que forwardLoop termine

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if ps.isPaused(ip) {
				continue
			}

			pinger, err := ping.NewPinger(ip)
			if err != nil {
				log.Printf("Erro ao criar pinger para %s: %v", ip, err)
				continue
			}

			pinger.Count = 1
			pinger.Timeout = 4 * time.Second
			pinger.SetPrivileged(true)

			err = pinger.Run()
			stats := pinger.Statistics()

			now := time.Now().Format(time.RFC3339)
			latency := -1.0
			online := false

			if err == nil && stats != nil && stats.PacketsRecv > 0 {
				latency = float64(stats.AvgRtt.Milliseconds())
				online = true
			} else if err != nil {
				log.Printf("Falha no ping para %s: %v", ip, err)
			}

			update := &pb.StatusUpdate{
				Ip:        ip,
				Online:    online,
				Latency:   latency,
				Status:    "ok",
				Timestamp: now,
			}

			// envio não bloqueante — evita congelar se o buffer encher
			select {
			case statusChan <- update:
			default:
				log.Printf("statusChan cheio — descartando update de %s", ip)
			}
		}
	}
}

////////////////////////////////////////////////////////////////////////////////
// MAIN
////////////////////////////////////////////////////////////////////////////////

func main() {
	lis, err := net.Listen("tcp", ":50051")
	if err != nil {
		log.Fatalf("Erro ao iniciar listener: %v", err)
	}

	grpcServer := grpc.NewServer()
	pb.RegisterPingServiceServer(grpcServer, NewPingServer())

	fmt.Println("gRPC PingService escutando em :50051")
	if err := grpcServer.Serve(lis); err != nil {
		log.Fatalf("Erro ao iniciar gRPC: %v", err)
	}
}
