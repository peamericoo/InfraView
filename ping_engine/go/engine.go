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

type serverStatus struct {
	cancel context.CancelFunc
	paused bool
}

type PingServer struct {
	pb.UnimplementedPingServiceServer
	mu       sync.Mutex
	servers  map[string]serverStatus
	statusCh map[string]chan *pb.StatusUpdate
}

func NewPingServer() *PingServer {
	return &PingServer{
		servers:  make(map[string]serverStatus),
		statusCh: make(map[string]chan *pb.StatusUpdate),
	}
}

func (ps *PingServer) AddServer(ctx context.Context, req *pb.AddRequest) (*pb.Ack, error) {
	ip := req.GetIp()

	ps.mu.Lock()
	defer ps.mu.Unlock()

	if _, exists := ps.servers[ip]; exists {
		return &pb.Ack{Success: false, Message: "Already exists"}, nil
	}

	ctxPing, cancel := context.WithCancel(context.Background())
	ps.servers[ip] = serverStatus{cancel: cancel, paused: false}
	ps.statusCh[ip] = make(chan *pb.StatusUpdate, 100)

	go ps.pingLoop(ctxPing, ip, ps.statusCh[ip])

	return &pb.Ack{Success: true, Message: "Added"}, nil
}

func (ps *PingServer) RemoveServer(ctx context.Context, req *pb.RemoveRequest) (*pb.Ack, error) {
	ip := req.GetIp()

	ps.mu.Lock()
	defer ps.mu.Unlock()

	status, exists := ps.servers[ip]
	if !exists {
		return &pb.Ack{Success: false, Message: "Not found"}, nil
	}

	status.cancel()
	delete(ps.servers, ip)
	delete(ps.statusCh, ip)

	return &pb.Ack{Success: true, Message: "Removed"}, nil
}

func (ps *PingServer) PauseServer(ctx context.Context, req *pb.PauseRequest) (*pb.Ack, error) {
	ip := req.GetIp()

	ps.mu.Lock()
	defer ps.mu.Unlock()

	status, exists := ps.servers[ip]
	if !exists {
		return &pb.Ack{Success: false, Message: "Not found"}, nil
	}

	status.paused = true
	ps.servers[ip] = status

	return &pb.Ack{Success: true, Message: "Paused"}, nil
}

func (ps *PingServer) ResumeServer(ctx context.Context, req *pb.ResumeRequest) (*pb.Ack, error) {
	ip := req.GetIp()

	ps.mu.Lock()
	defer ps.mu.Unlock()

	status, exists := ps.servers[ip]
	if !exists {
		return &pb.Ack{Success: false, Message: "Not found"}, nil
	}

	status.paused = false
	ps.servers[ip] = status

	return &pb.Ack{Success: true, Message: "Resumed"}, nil
}

func (ps *PingServer) StreamStatus(req *pb.StatusRequest, stream pb.PingService_StreamStatusServer) error {
	for {
		ps.mu.Lock()
		chans := []<-chan *pb.StatusUpdate{}
		for _, ch := range ps.statusCh {
			chans = append(chans, ch)
		}
		ps.mu.Unlock()

		for _, ch := range chans {
			select {
			case update := <-ch:
				if err := stream.Send(update); err != nil {
					log.Printf("Erro ao enviar update: %v", err)
				}
			default:
			}
		}
		time.Sleep(500 * time.Millisecond)
	}
}

func (ps *PingServer) pingLoop(ctx context.Context, ip string, statusChan chan<- *pb.StatusUpdate) {
	for {
		select {
		case <-ctx.Done():
			return
		default:
			ps.mu.Lock()
			status := ps.servers[ip]
			paused := status.paused
			ps.mu.Unlock()

			if !paused {
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

				if err == nil && stats.PacketsRecv > 0 {
					latency = float64(stats.AvgRtt.Milliseconds())
					online = true
				} else {
					log.Printf("Falha no ping para %s: %v", ip, err)
				}

				status := &pb.StatusUpdate{
					Ip:        ip,
					Online:    online,
					Latency:   latency,
					Status:    "ok",
					Timestamp: now,
				}
				statusChan <- status
			}

			time.Sleep(2 * time.Second)
		}
	}
}

func main() {
	listener, err := net.Listen("tcp", ":50051")
	if err != nil {
		log.Fatalf("Erro ao iniciar listener: %v", err)
	}

	grpcServer := grpc.NewServer()
	pb.RegisterPingServiceServer(grpcServer, NewPingServer())

	fmt.Println("gRPC PingService escutando em :50051")
	if err := grpcServer.Serve(listener); err != nil {
		log.Fatalf("Erro ao iniciar gRPC: %v", err)
	}
}
