import concurrent.futures
import requests
import uuid
from app import create_app
from app.models import db, RetiradaDependente, RetiradaJovemAprendiz, EstoqueKit

BASE_URL = "http://127.0.0.1:5000"

ADMIN_EMAIL = "admin@funfarme.com.br"
ADMIN_SENHA = "admin123"

OP2_EMAIL = "operador1@funfarme.com.br"
OP2_SENHA = "admin123"

MODELO_TESTE = "Abelha"


def criar_sessao():
    return requests.Session()


def autenticar(session, email, senha):
    resp = session.post(
        f"{BASE_URL}/api/login",
        json={"email": email, "senha": senha}
    )
    return resp.status_code == 200, resp.text


def cadastrar_operador_se_necessario(sessao_admin):
    sessao_admin.post(
        f"{BASE_URL}/api/criar-usuario",
        json={
            "nome": "Operador 1",
            "email": OP2_EMAIL,
            "senha": OP2_SENHA,
            "perfil": "OPERADOR"
        }
    )


def obter_ou_criar_codigos_retirada():
    """Garante via banco a existência de 2 registros de retirada reais para o teste."""
    app = create_app()
    with app.app_context():
        # 1. Garante que o modelo de teste existe no estoque
        est = EstoqueKit.query.filter_by(codigo_kit=MODELO_TESTE).first()
        if not est:
            est = EstoqueKit(
                codigo_kit=MODELO_TESTE,
                descricao_kit=f"Kit {MODELO_TESTE}",
                quantidade_disponivel=1,
                quantidade_baixada=0,
                quantidade_reservada=0,
                ativo=True
            )
            db.session.add(est)
            db.session.commit()

        # 2. Busca registros pendentes existentes
        deps = RetiradaDependente.query.filter(RetiradaDependente.status != 'ENTREGUE').limit(2).all()
        codigos = [d.codigo_retirada for d in deps]

        if len(codigos) < 2:
            jovens = RetiradaJovemAprendiz.query.filter(RetiradaJovemAprendiz.status != 'ENTREGUE').limit(2 - len(codigos)).all()
            codigos.extend([j.codigo_retirada for j in jovens])

        # 3. Se ainda faltar, cria temporários para o teste
        while len(codigos) < 2:
            novo_cod = f"TESTE_{uuid.uuid4().hex[:8].upper()}"
            novo_reg = RetiradaDependente(
                codigo_retirada=novo_cod,
                id_colaborador=999000 + len(codigos),
                nome_colaborador=f"Beneficiario Teste {len(codigos) + 1}",
                qtd_kits=1,
                resumo_kits="Kits Automáticos (Órfãos)",
                status="PENDENTE"
            )
            db.session.add(novo_reg)
            db.session.commit()
            codigos.append(novo_cod)

        return codigos[0], codigos[1]


def enviar_baixa(session, payload, operador_nome):
    resp = session.post(f"{BASE_URL}/api/dar-baixa-item", json=payload)
    try:
        dados = resp.json()
        msg = dados.get("mensagem", resp.text)
    except Exception:
        msg = resp.text
    return f"[{operador_nome}] HTTP {resp.status_code} -> {msg}"


def main():
    print("1. Efetuando login do Administrador...")
    sessao_admin = criar_sessao()
    sucesso, msg = autenticar(sessao_admin, ADMIN_EMAIL, ADMIN_SENHA)
    if not sucesso:
        print(f"Erro ao logar com Admin: {msg}")
        return

    print("2. Garantindo cadastro do Operador 2...")
    cadastrar_operador_se_necessario(sessao_admin)

    print("3. Efetuando login do Operador 2...")
    sessao_op2 = criar_sessao()
    sucesso_op2, msg_op2 = autenticar(sessao_op2, OP2_EMAIL, OP2_SENHA)
    if not sucesso_op2:
        print(f"Erro ao logar com Operador 2: {msg_op2}")
        return

    print("4. Obtendo/Garantindo registros reais no banco...")
    cod1, cod2 = obter_ou_criar_codigos_retirada()
    print(f"   Cartão 1: {cod1}")
    print(f"   Cartão 2: {cod2}")

    payload_op1 = {
        "codigo_retirada": cod1,
        "index_kit": 0,
        "modelo_baixa": MODELO_TESTE,
        "nome_dependente": "Filho Operador A"
    }

    payload_op2 = {
        "codigo_retirada": cod2,
        "index_kit": 0,
        "modelo_baixa": MODELO_TESTE,
        "nome_dependente": "Filho Operador B"
    }

    print(f"\n5. Disparando baixas concorrentes simultâneas para '{MODELO_TESTE}'...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(enviar_baixa, sessao_admin, payload_op1, "Operador A (Admin)")
        f2 = executor.submit(enviar_baixa, sessao_op2, payload_op2, "Operador B")

        print(f1.result())
        print(f2.result())


if __name__ == "__main__":
    main()