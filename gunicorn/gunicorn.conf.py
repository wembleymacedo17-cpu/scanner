import multiprocessing

# Endereço interno de escuta (comunicação com Nginx)
bind = "127.0.0.1:5000"

# Dimensionamento para 10 celulares em instância de 2 vCPUs
workers = 3
worker_class = "gthread"
threads = 4

# Controle de conexões e filas
backlog = 2048
timeout = 30
keepalive = 5

# Reciclagem preventiva de workers para mitigar vazamentos de memória
max_requests = 1000
max_requests_jitter = 50

# Logs da aplicação
accesslog = "-"
errorlog = "-"
loglevel = "info"