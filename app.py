import streamlit as st
import pandas as pd
import pdfplumber
from openai import OpenAI
import io

# Configuração inicial da página
st.set_page_config(page_title="Analisador de Editais 🎯", layout="wide")

def extrair_texto_pdf(arquivos_pdf):
    """Extrai e concatena o texto de até 3 PDFs, limitando a 10.000 caracteres."""
    texto_completo = ""
    for arquivo in arquivos_pdf:
        try:
            with pdfplumber.open(arquivo) as pdf:
                for pagina in pdf.pages:
                    texto_extraido = pagina.extract_text()
                    if texto_extraido:
                        texto_completo += texto_extraido + "\n"
        except Exception as e:
            st.error(f"Erro ao ler o arquivo {arquivo.name}: {e}")
    return texto_completo[:10000]

def carregar_dados_csv(arquivo_csv):
    """Carrega o arquivo CSV enviado pelo usuário."""
    if arquivo_csv is None:
        return None

    try:
        conteudo = arquivo_csv.read().decode('utf-8')
        df = pd.read_csv(io.StringIO(conteudo), sep=';', quotechar='"')
        return df
    except Exception as e:
        st.error(f"Erro ao carregar o CSV: {e}")
        return None

def inicializar_sessao():
    """Inicializa as variáveis de sessão."""
    if 'dados_carregados' not in st.session_state:
        st.session_state.dados_carregados = False
    if 'df_perguntas' not in st.session_state:
        st.session_state.df_perguntas = None
    if 'api_key' not in st.session_state:
        st.session_state.api_key = ""
    if 'edital_selecionado' not in st.session_state:
        st.session_state.edital_selecionado = None
    if 'perguntas_filtradas' not in st.session_state:
        st.session_state.perguntas_filtradas = []
    if 'csv_file_name' not in st.session_state:
        st.session_state.csv_file_name = None

def main():
    inicializar_sessao()

    st.title("📄 Analisador de Editais com IA 🎯")
    st.markdown("""
    Este aplicativo analisa seus documentos PDF e responde perguntas automáticas baseadas nos editais
    cadastrados no arquivo `bd.csv` que você fará upload.
    """)

    # --- BARRA LATERAL ---
    st.sidebar.header("🔧 Configurações e Dados")

    # 1. Chave da API
    st.sidebar.subheader("1. Chave da API DeepSeek")
    api_key_input = st.sidebar.text_input(
        "Cole sua chave da API DeepSeek",
        type="password",
        placeholder="sk-...",
        help="Insira sua chave de API do DeepSeek"
    )

    # 2. Upload do CSV
    st.sidebar.subheader("2. Arquivo de Perguntas (bd.csv)")
    arquivo_csv = st.sidebar.file_uploader(
        "Faça upload do arquivo bd.csv",
        type="csv",
        help="Arquivo CSV com as perguntas no formato: edital;pergunta;"
    )

    # 3. Botões
    st.sidebar.subheader("3. Confirmar e Carregar")

    col1, col2 = st.sidebar.columns(2)
    with col1:
        botao_carregar = st.button("📥 Carregar Dados", use_container_width=True)
    with col2:
        if st.button("🗑️ Limpar", use_container_width=True):
            st.session_state.dados_carregados = False
            st.session_state.df_perguntas = None
            st.session_state.api_key = ""
            st.session_state.edital_selecionado = None
            st.session_state.perguntas_filtradas = []
            st.session_state.csv_file_name = None
            st.rerun()

    # Processar carregamento
    if botao_carregar:
        erros = []

        if not api_key_input or api_key_input.strip() == "":
            erros.append("❌ Insira sua chave da API DeepSeek")
        else:
            st.session_state.api_key = api_key_input.strip()

        if arquivo_csv is None:
            erros.append("❌ Faça upload do arquivo bd.csv")
        else:
            df = carregar_dados_csv(arquivo_csv)
            if df is not None:
                st.session_state.df_perguntas = df
                st.session_state.csv_file_name = arquivo_csv.name
            else:
                erros.append("❌ Erro ao processar o CSV")

        if not erros:
            st.session_state.dados_carregados = True
            st.sidebar.success("✅ Dados carregados!")
        else:
            for erro in erros:
                st.sidebar.error(erro)

    # Status
    if st.session_state.dados_carregados:
        st.sidebar.success("✅ Dados carregados com sucesso!")
        st.sidebar.info(f"CSV: {st.session_state.csv_file_name}")
    else:
        st.sidebar.warning("⚠️ Aguardando carregamento...")

    st.sidebar.divider()

    # Upload de PDFs
    st.sidebar.subheader("📄 Documentos do Proponente")
    uploaded_files = st.sidebar.file_uploader(
        "Faça upload de até 3 PDFs",
        type="pdf",
        accept_multiple_files=True
    )
    if uploaded_files and len(uploaded_files) > 3:
        st.sidebar.warning("⚠️ Apenas os 3 primeiros serão processados.")
        uploaded_files = uploaded_files[:3]

    # --- ÁREA PRINCIPAL ---
    if not st.session_state.dados_carregados:
        st.info("👈 **Para começar, complete as etapas na barra lateral:**\n\n"
                "1. Cole sua chave da API DeepSeek\n"
                "2. Faça upload do arquivo `bd.csv`\n"
                "3. Clique em **'Carregar Dados'**")
        return

    df_perguntas = st.session_state.df_perguntas
    api_key = st.session_state.api_key

    if df_perguntas is not None:
        editais_disponiveis = df_perguntas['edital'].unique()
        edital_selecionado = st.selectbox(
            "📌 Selecione o Edital para análise:",
            editais_disponiveis
        )

        perguntas_filtradas = df_perguntas[df_perguntas['edital'] == edital_selecionado]['pergunta'].tolist()

        st.info(f"📋 O sistema responderá **{len(perguntas_filtradas)} perguntas**.")

        with st.expander("👁️ Visualizar perguntas do edital"):
            for idx, p in enumerate(perguntas_filtradas, 1):
                st.write(f"{idx}. {p}")

        # Botão Gerar Respostas
        if st.button("🚀 Gerar Respostas", type="primary", use_container_width=True):
            if not uploaded_files:
                st.error("❌ Faça upload de pelo menos um PDF do proponente.")
            elif not api_key:
                st.error("❌ Chave da API não encontrada.")
            else:
                with st.spinner("📄 Extraindo texto e consultando IA..."):
                    contexto_pdf = extrair_texto_pdf(uploaded_files)

                    if not contexto_pdf.strip():
                        st.error("❌ Não foi possível extrair texto dos PDFs.")
                    else:
                        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

                        st.subheader("📊 Resultados da Avaliação")

                        for i, pergunta in enumerate(perguntas_filtradas):
                            with st.spinner(f"Processando {i+1}/{len(perguntas_filtradas)}..."):
                                try:
                                    response = client.chat.completions.create(
                                        model="deepseek-chat",
                                        messages=[
                                            {
                                                "role": "system",
                                                "content": (
                                                    "Você é um AVALIADOR CRÍTICO E RIGOROSO de editais culturais.\n\n"
                                                    "REGRAS:\n"
                                                    "1. Seja EXIGENTE e DESCONFIADO.\n"
                                                    "2. Nota máxima só para projetos EXCEPCIONAIS.\n"
                                                    "3. Aponte FORÇOS e FRACOS.\n"
                                                    "4. Use termos como 'insuficiente', 'frágil', 'inconsistente'.\n\n"
                                                    "FORMATO: Nota: X - FORÇOS: [lista] / FRACOS: [lista] - Justificativa.\n"
                                                    "Para perguntas sem nota: responda com UMA frase curta."
                                                )
                                            },
                                            {
                                                "role": "user",
                                                "content": f"Contexto:\n{contexto_pdf}\n\nPergunta:\n{pergunta}"
                                            }
                                        ],
                                        stream=False,
                                        max_tokens=350,
                                        temperature=0.2
                                    )

                                    resposta_texto = response.choices[0].message.content

                                    with st.expander(f"📌 Pergunta {i+1}: {pergunta[:100]}{'...' if len(pergunta) > 100 else ''}", expanded=False):
                                        st.markdown(f"**Resposta:** {resposta_texto}")
                                        st.divider()

                                except Exception as e:
                                    st.error(f"❌ Erro na pergunta {i+1}: {str(e)[:150]}")

                        st.success("✅ Avaliação concluída!")

if __name__ == "__main__":
    main()
