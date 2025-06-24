# InfraView

InfraView é uma aplicação para monitoramento de servidores, com interface gráfica moderna baseada em PyQt5 e visualização de dados com matplotlib.

## Requisitos

- Python 3.10 ou 3.11 (recomendado)
- Pip (gerenciador de pacotes Python)

## Instalação

1. **Clone o repositório:**

   ```sh
   git clone https://github.com/seu-usuario/InfraView.git
   cd InfraView
   ```

2. **(Opcional) Crie um ambiente virtual:**

   ```sh
   python -m venv .venv
   # Ative o ambiente virtual:
   # No Windows:
   .venv\Scripts\activate
   # No Linux/Mac:
   source .venv/bin/activate
   ```

3. **Instale as dependências:**

   ```sh
   pip install -r requirements.txt
   ```

## Execução

1. **Execute a aplicação:**

   ```sh
   python run.py
   ```

   Ou, se preferir, execute diretamente o arquivo principal:

   ```sh
   python core/main.py
   ```

2. **A interface gráfica será aberta.**

   - Utilize os botões para adicionar, editar e monitorar servidores.
   - Visualize o status dos servidores e falhas em tempo real.

## Estrutura do Projeto

- `core/` — Lógica principal e utilitários
- `gui/` — Componentes da interface gráfica
- `assets/` — Ícones e arquivos de mídia
- `data/` — Banco de dados e arquivos de configuração

## Observações

- Certifique-se de que o Python está corretamente instalado e configurado no PATH.
- Para melhor compatibilidade, utilize Python 3.10 ou 3.11.
- Caso utilize ambiente virtual, sempre ative antes de instalar dependências ou executar o projeto.

---

**Dúvidas ou problemas?**  
Abra uma issue no repositório ou entre em contato