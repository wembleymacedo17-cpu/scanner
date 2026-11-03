from app import create_app

# Cria a instância da aplicação Flask
app = create_app()

if __name__ == '__main__':
    # host='0.0.0.0' permite aceder à página a partir do telemóvel/tablet na mesma rede Wi-Fi
    # port=5000 define a porta de execução
    # debug=True reinicia o servidor automaticamente ao alterar ficheiros em desenvolvimento
    app.run(host='0.0.0.0', port=5000, debug=True)
    