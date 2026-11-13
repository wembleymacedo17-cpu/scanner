import os
import sys
import random
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text

# 1. Garante que a raiz do projeto (Baixas_Qrcode) esteja no path
diretorio_atual = os.path.dirname(os.path.abspath(__file__))
raiz_projeto = os.path.abspath(os.path.join(diretorio_atual, '..', '..'))
if raiz_projeto not in sys.path:
    sys.path.insert(0, raiz_projeto)

env_path = os.path.join(raiz_projeto, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

from app.models import (
    db,
    RetiradaDependente,
    RetiradaJovemAprendiz,
    Usuario,
    HistoricoBaixa,
    EstoqueKit,
    MovimentacaoEstoque
)
from app.services.estoque_service import recalibrar_estoque


def limpar_str(valor):
    """Converte valores nulos ou NaN do Pandas em None e remove espaços extras."""
    if valor is None or pd.isna(valor):
        return None
    texto = str(valor).strip()
    return None if texto in ('', 'nan', 'None') else texto


def buscar_arquivo(nomes_candidatos: list) -> str | None:
    """Procura o primeiro arquivo existente na raiz do projeto ou um nível acima."""
    for nome in nomes_candidatos:
        for base in (raiz_projeto, os.path.abspath(os.path.join(raiz_projeto, '..'))):
            caminho = os.path.join(base, nome)
            if os.path.exists(caminho):
                return caminho
    return None


def ler_csv_seguro(caminho_csv: str) -> pd.DataFrame:
    """Lê CSV detectando separador (; ou ,) e removendo BOM (\ufeff) das colunas."""
    with open(caminho_csv, 'r', encoding='utf-8-sig') as f:
        primeira_linha = f.readline()
    separador = ';' if primeira_linha.count(';') > primeira_linha.count(',') else ','

    df = pd.read_csv(caminho_csv, sep=separador, encoding='utf-8-sig')
    df.columns = [str(col).replace('\ufeff', '').strip() for col in df.columns]
    return df


def gerar_novo_id_retirada(id_atual: int, ids_usados: set) -> int:
    """Concatena o id_retirada atual + 4 dígitos aleatórios garantindo unicidade."""
    while True:
        sufixo_4_digitos = random.randint(1000, 9999)
        novo_id = int(f"{id_atual}{sufixo_4_digitos}")
        if novo_id not in ids_usados:
            ids_usados.add(novo_id)
            return novo_id


def carregar_dados_iniciais(limpar_antes=False):
    """
    Executa a carga de dados:
    - Se limpar_antes=True: faz HARD RESET nas tabelas, zera baixas e recarrega tudo.
    - Se limpar_antes=False: só popula se o banco estiver vazio (uso no boot da aplicação).
    """
    if not limpar_antes and (Usuario.query.first() or RetiradaDependente.query.first()):
        print("ℹ️ Banco já possui registros cadastrados. Pulando carga para evitar duplicações.")
        return

    if limpar_antes:
        print("🧨 Executando HARD RESET no banco de dados...")
        try:
            db.session.execute(text("""
                TRUNCATE TABLE 
                    historico_baixas, 
                    movimentacoes_estoque, 
                    retiradas_dependentes, 
                    retiradas_jovens_aprendizes, 
                    usuarios 
                RESTART IDENTITY CASCADE;
            """))
        except Exception:
            db.session.rollback()
            HistoricoBaixa.query.delete()
            MovimentacaoEstoque.query.delete()
            RetiradaDependente.query.delete()
            RetiradaJovemAprendiz.query.delete()
            Usuario.query.delete()

        EstoqueKit.query.update({EstoqueKit.quantidade_baixada: 0})
        db.session.commit()
        print("✅ Tabelas limpas e sequences reiniciadas!")

    # -------------------------------------------------------------
    # 1. CRIAÇÃO DO ADMINISTRADOR MASTER (.ENV)
    # -------------------------------------------------------------
    admin_nome = os.getenv('ADMIN_DEFAULT_NOME', 'Administrador Principal')
    admin_email_env = os.getenv('ADMIN_DEFAULT_EMAIL')
    admin_pass = os.getenv('ADMIN_DEFAULT_PASS')

    if admin_email_env and admin_pass:
        admin_email = admin_email_env.lower().strip()
        admin = Usuario(
            nome=admin_nome,
            email=admin_email,
            perfil='ADMIN'
        )
        admin.set_senha(admin_pass)
        db.session.add(admin)
        db.session.commit()
        print(f"✅ Administrador Master criado! (Email: {admin_email})")
    else:
        print("⚠️ Variáveis de ADMIN padrão não encontradas no .env.")

    # -------------------------------------------------------------
    # 2. CARGA DE JOVENS APRENDIZES (CSV)
    # -------------------------------------------------------------
    caminho_csv = buscar_arquivo([
        'retiradas_jovens_enriquecida.csv',
        'retiradas_jovens.csv'
    ])

    if caminho_csv:
        print(f"📦 Importando Jovens Aprendizes de: {os.path.basename(caminho_csv)}...")
        df_jovens = ler_csv_seguro(caminho_csv)
        df_jovens = df_jovens.where(pd.notnull(df_jovens), None)

        ids_gerados = set()
        qtd_jovens = 0

        for _, row in df_jovens.iterrows():
            id_original = int(row['id_retirada'])
            novo_id_retirada = gerar_novo_id_retirada(id_original, ids_gerados)

            registro = RetiradaJovemAprendiz(
                id_retirada=novo_id_retirada,
                codigo_retirada=str(row['codigo_retirada']),
                id_colaborador=int(row['id_colaborador']),
                titulo_cargo=limpar_str(row.get('TITULO_CARGO') or row.get('titulo_cargo')),
                titulo_centro_custo=limpar_str(row.get('TITULO_CENTRO_CUSTO') or row.get('titulo_centro_custo')),
                nome_filial=limpar_str(row.get('NOME_FILIAL') or row.get('nome_filial')),
                email=limpar_str(row.get('email')),
                telefone=limpar_str(row.get('telefone')),
                qtd_kits=int(row['qtd_kits']),
                resumo_kits=str(row['resumo_kits']),
                status=str(row['status']),
                data_geracao=limpar_str(row.get('data_geracao'))
            )
            db.session.add(registro)
            qtd_jovens += 1

        db.session.commit()
        print(f"✅ {qtd_jovens} registros de Jovens Aprendizes inseridos (com novos IDs aleatórios)!")
    else:
        print("⚠️ Nenhum arquivo CSV de Jovens Aprendizes encontrado.")

    # -------------------------------------------------------------
    # 3. CARGA DE DEPENDENTES (EXCEL)
    # -------------------------------------------------------------
    caminho_excel = buscar_arquivo([
        'retiradas_enriquecida_senior.xlsx',
        'retiradas_padronizada_corrigida.xlsx'
    ])

    if caminho_excel:
        print(f"📦 Importando Dependentes de: {os.path.basename(caminho_excel)}...")
        df_dep = pd.read_excel(caminho_excel)
        df_dep.columns = [str(col).replace('\ufeff', '').strip() for col in df_dep.columns]
        df_dep = df_dep.where(pd.notnull(df_dep), None)

        qtd_dep = 0
        for _, row in df_dep.iterrows():
            registro = RetiradaDependente(
                id_retirada=int(row['id_retirada']),
                codigo_retirada=str(row['codigo_retirada']),
                id_colaborador=int(row['id_colaborador']),
                nome_colaborador=limpar_str(row.get('nome_colaborador')),
                titulo_cargo=limpar_str(row.get('TITULO_CARGO') or row.get('titulo_cargo')),
                titulo_centro_custo=limpar_str(row.get('TITULO_CENTRO_CUSTO') or row.get('titulo_centro_custo')),
                nome_filial=limpar_str(row.get('NOME_FILIAL') or row.get('nome_filial')),
                log_modificacao_cracha=limpar_str(row.get('log_modificacao_cracha')),
                email=limpar_str(row.get('email')),
                telefone=limpar_str(row.get('telefone')),
                qtd_kits=int(row['qtd_kits']),
                resumo_kits=str(row['resumo_kits']),
                status=str(row['status']),
                data_geracao=limpar_str(row.get('data_geracao')),
                necessita_recontato=limpar_str(row.get('necessita_recontato')),
                motivo_recontato=limpar_str(row.get('motivo_recontato'))
            )
            db.session.add(registro)
            qtd_dep += 1

        db.session.commit()
        print(f"✅ {qtd_dep} registros de Dependentes inseridos!")
    else:
        print("⚠️ Nenhum arquivo Excel de Dependentes encontrado.")

    # -------------------------------------------------------------
    # 4. RECALIBRAÇÃO AUTOMÁTICA DAS RESERVAS DE ESTOQUE
    # -------------------------------------------------------------
    print("🔄 Recalibrando reservas por modelo com base nos cartões importados...")
    res_calibragem = recalibrar_estoque()
    print(f"✅ Estoque calibrado! Reservas garantidas: {res_calibragem['total_reservas_garantidas']} un.")


if __name__ == '__main__':
    from app import create_app
    app = create_app()
    with app.app_context():
        carregar_dados_iniciais(limpar_antes=True)