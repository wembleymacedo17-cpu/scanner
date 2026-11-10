#!/bin/bash
set -e

echo "============================================================"
echo "🚀 INICIANDO INSTALAÇÃO E CONFIGURAÇÃO AUTOMÁTICA NA AWS EC2"
echo "============================================================"

# 1. Atualização e instalação de pacotes essenciais
echo "📦 1. Instalando Nginx e Certbot..."
sudo apt update -y
sudo apt install -y nginx certbot python3-certbot-nginx

# 2. Configuração do Serviço Systemd
echo "⚙️ 2. Ativando o serviço Gunicorn (Systemd)..."
sudo cp kitescolar.service /etc/systemd/system/kitescolar.service
sudo systemctl daemon-reload
sudo systemctl enable kitescolar
sudo systemctl restart kitescolar

# 3. Configuração do Nginx
echo "🌐 3. Publicando a rota no Nginx..."
sudo cp nginx_kitescolar.conf /etc/nginx/sites-available/kitescolar
sudo ln -sf /etc/nginx/sites-available/kitescolar /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Validação e recarga do Nginx
sudo nginx -t
sudo systemctl reload nginx

echo "============================================================"
echo "🎉 DEPLOY DE SISTEMA CONCLUÍDO COM SUCESSO!"
echo "➡️  Para ativar o SSL (HTTPS) com o seu domínio, execute:"
echo "    sudo certbot --nginx -d seu_subdominio.com.br"
echo "============================================================"