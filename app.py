import streamlit as st
import pandas as pd
import pdfplumber
from openai import OpenAI
import io

# Configuração inicial da página
st.set_page_config(page_title="Analisador de Editais", layout="wide")

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

    # --- BARRA LATERAL: Configuração e CSV ---
    st.sidebar.header("🔧 Configuração Inicial")
    
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
    st.sidebar.info("ℹ️ Após carregar os dados, faça upload dos PDFs na área principal.")
    
    # --- ÁREA PRINCIPAL: Upload de PDFs e análise ---
    
    if not st.session_state.dados_carregados:
        st.info("👈 **Para começar, complete as etapas na barra lateral:**\n\n"
                "1. Cole sua chave da API DeepSeek\n"
                "2. Faça upload do arquivo `bd.csv`\n"
                "3. Clique em **'Carregar Dados'**")
        return
    
    # --- UPLOAD DE PDFs NA ÁREA PRINCIPAL ---
    st.subheader("📄 Documentos do Proponente (PDF)")
    st.markdown("Faça upload dos documentos do projeto que será avaliado (formulário de inscrição, currículos, anexos, etc.)")
    
    uploaded_files = st.file_uploader(
        "📁 Selecione até 3 arquivos PDF",
        type="pdf",
        accept_multiple_files=True,
        help="Envie os PDFs do projeto que será avaliado"
    )
    
    if uploaded_files and len(uploaded_files) > 3:
        st.warning("⚠️ Apenas os 3 primeiros arquivos serão processados.")
        uploaded_files = uploaded_files[:3]
    
    # Mostrar arquivos enviados
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} arquivo(s) carregado(s):")
        for f in uploaded_files:
            st.write(f"   📄 {f.name} ({round(f.size/1024, 1)} KB)")
    
    st.divider()
    
    # Seleção do edital e perguntas
    df_perguntas = st.session_state.df_perguntas
    api_key = st.session_state.api_key
    
    if df_perguntas is not None:
        editais_disponiveis = df_perguntas['edital'].unique()
        edital_selecionado = st.selectbox(
            "📌 Selecione o Edital para análise:",
            editais_disponiveis
        )
        
        perguntas_filtradas = df_perguntas[df_perguntas['edital'] == edital_selecionado]['pergunta'].tolist()
        st.session_state.perguntas_filtradas = perguntas_filtradas
        
        st.info(f"📋 O sistema responderá **{len(perguntas_filtradas)} perguntas** baseadas nos PDFs enviados.")
        
        with st.expander("👁️ Visualizar perguntas do edital"):
            for idx, p in enumerate(perguntas_filtradas, 1):
                st.write(f"{idx}. {p}")
        
        # --- Botão de Processamento ---
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            botao_gerar = st.button("🚀 Gerar Respostas", type="primary", use_container_width=True)
        
        if botao_gerar:
            if not uploaded_files:
                st.error("❌ Por favor, faça upload de pelo menos um arquivo PDF do proponente.")
            elif not api_key:
                st.error("❌ Chave da API não encontrada. Recarregue os dados na barra lateral.")
            else:
                with st.spinner("📄 Extraindo texto dos PDFs e consultando a IA..."):
                    contexto_pdf = extrair_texto_pdf(uploaded_files)
                    
                    if not contexto_pdf.strip():
                        st.error("❌ Não foi possível extrair texto dos PDFs. Verifique se são arquivos de texto e não apenas imagens.")
                    else:
                        # Mostrar preview do contexto extraído (opcional)
                        with st.expander("🔍 Preview do texto extraído (primeiros 500 caracteres)"):
                            st.text(contexto_pdf[:500] + "...")
                        
                        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
                        
                        st.subheader("📊 Resultados da Avaliação")
                        st.markdown("---")
                        
                        # Barra de progresso
                        progress_bar = st.progress(0)
                        
                        for i, pergunta in enumerate(perguntas_filtradas):
                            progress_bar.progress((i + 1) / len(perguntas_filtradas))
                            
                            with st.spinner(f"Processando pergunta {i+1}/{len(perguntas_filtradas)}..."):
                                try:
                                    response = client.chat.completions.create(
                                        model="deepseek-chat",
                                        messages=[
                                            {
                                                "role": "system",
                                                "content": (
                                                    "Você é um AVALIADOR CRÍTICO E RIGOROSO de editais culturais, membro da comissão de avaliação.\n\n"
                                                    "REGRAS OBRIGATÓRIAS DE AVALIAÇÃO (TOM CRÍTICO):\n"
                                                    "1. Seja EXIGENTE e DESCONFIADO. Não assuma que o projeto é bom por padrão.\n"
                                                    "2. A nota máxima só deve ser dada para projetos EXCEPCIONAIS, com evidências concretas.\n"
                                                    "3. Para cada nota, aponte equilíbrio entre PONTOS FORTES e PONTOS FRACOS.\n"
                                                    "4. Desconfie de: informações vagas, promessas sem detalhamento, orçamentos incoerentes, cronogramas irreais.\n"
                                                    "5. Se faltarem informações essenciais, REDUZA A NOTA e mencione a deficiência.\n"
                                                    "6. Seja direto e incisivo. Use termos como 'insuficiente', 'não comprovado', 'frágil', 'inconsistente'.\n\n"
                                                    "FORMATO OBRIGATÓRIO (para perguntas com nota):\n"
                                                    "Nota: X - FORÇOS: [lista] / FRACOS: [lista] - Justificativa final.\n\n"
                                                    "Para perguntas sem nota (nome, título, sim/não): responda com UMA única frase curta.\n"
                                                    "Para o resumo crítico: três parágrafos (máximo 7 linhas cada) com análise de riscos e inconsistências."
                                                )
                                            },
                                            {
                                                "role": "user", 
                                                "content": f"Documentos do proponente (formulário de inscrição e anexos):\n{contexto_pdf}\n\nPergunta do avaliador:\n{pergunta}"
                                            }
                                        ],
                                        stream=False,
                                        max_tokens=400,
                                        temperature=0.2
                                    )
                                    
                                    resposta_texto = response.choices[0].message.content
                                    
                                    # Expansor para cada resposta
                                    with st.expander(f"📌 Pergunta {i+1}: {pergunta[:100]}{'...' if len(pergunta) > 100 else ''}", expanded=False):
                                        st.markdown(f"**Pergunta completa:** {pergunta}")
                                        st.markdown("**Resposta:**")
                                        st.markdown(f"> {resposta_texto}")
                                        st.divider()
                                        
                                except Exception as e:
                                    st.error(f"❌ Erro ao processar a pergunta {i+1}: {str(e)[:200]}")
                        
                        progress_bar.empty()
                        st.success("✅ Avaliação concluída com sucesso!")
                        st.balloons()

if __name__ == "__main__":
    main()
