import re
import json
import os
from io import BytesIO
from typing import List, Dict
import streamlit as st
from pypdf import PdfReader

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

st.set_page_config(
    page_title="Detector de Novo Endereço",
    page_icon="📄",
    layout="wide",
)

# =========================================================
# PADRÕES REGEX
# =========================================================

PADROES_FALHA_FORTE = [
    r"n[aã]o\s+foi\s+poss[ií]vel\s+proceder\s+[àa]\s+cita[cç][aã]o",
    r"n[aã]o\s+foi\s+poss[ií]vel\s+proceder\s+[àa]\s+intima[cç][aã]o",
    r"mandado\s+n[aã]o\s+cumprido",
    r"mandado\s+n[aã]o\s+entregue",
    r"cumprimento\s+negativo",
    r"retorno\s+de\s+mandado",
    r"retorno\s+negativo\s+do\s+mandado",
    r"devolu[cç][aã]o\s+de\s+mandado\s+n[aã]o\s+cumprido",
    r"sem\s+cumprimento",
    r"juntado\s+aos\s+autos\s+sem\s+cumprimento",
    r"mandado\s+.{0,30}juntado\s+.{0,30}sem\s+cumprimento",
    r"certid[aã]o\s+negativa\s+do\s+oficial\s+de\s+justi[cç]a",
    r"certid[õo][eê]s\s+negativa[s]?\s+do\s+oficial\s+de\s+justi[cç]a",
    r"certid[aã]o\(?[õo]es?\)?\s+negativa\(?s?\)?\s+do\s+oficial",
    r"ar[s]?\s+assinada[s]?\s+por\s+3[oº°]",
    r"ar[s]?\s+assinado[s]?\s+por\s+3[oº°]",
    r"aviso[s]?\s+de\s+recebimento\s+assinado[s]?\s+por\s+terceiro",
    r"assinada[s]?\s+por\s+3[oº°]\s*,?\s+para\s+que",
    r"certid[aã]o\s+negativa",
]

PADROES_MOTIVO_LOCALIZACAO = [
    r"desconhecid[oa]\s+no\s+endere[cç]o",
    r"im[oó]vel\s+se\s+encontrava\s+desocupado",
    r"sem\s+moradores",
    r"local\s+est[aá]\s+sempre\s+fechado",
    r"mudou-?se",
    r"n[aã]o\s+reside\s+no\s+local",
    r"endere[cç]o\s+insuficiente",
    r"endere[cç]o\s+incorreto",
    r"endere[cç]o\s+n[aã]o\s+localizado",
    r"residente\s+em\s+local\s+incerto",
    r"n[aã]o\s+localizad[oa]",
    r"n[aã]o\s+encontrad[oa]",
    r"tomado\s+por\s+vegeta[cç][aã]o",
    r"aparentemente\s+sem\s+moradores",
    r"im[oó]vel\s+vazio",
    r"im[oó]vel\s+abandonado",
    r"ningu[eé]m\s+atendeu",
    r"porta\s+fechada",
    r"n[aã]o\s+foi\s+atendido",
]

PADROES_PROVIDENCIA = [
    r"requer[ae][ir]?\s+o\s+que\s+entender\s+de\s+direito",
    r"requer[ae][ir]?\s+o\s+que\s+entend[ae]r\s+de\s+direito",
    r"prosseguimento\s+do\s+feito",
    r"andamento\s+do\s+feito",
    r"dar\s+andamento\s+ao\s+feito",
    r"termos\s+de\s+prosseguimento",
    r"indicar\s+novo\s+endere[cç]o",
    r"informar\s+(?:novo[s]?\s+)?endere[cç]o[s]?",
    r"caso\s+venha\s+a\s+informar\s+novo[s]?\s+endere[cç]o[s]?",
    r"endere[cç]o\s+atualizado",
    r"novo[s]?\s+endere[cç]o[s]?",
    r"nova\s+dilig[êe]ncia",
    r"nova\s+tentativa\s+de\s+cita[cç][aã]o",
    r"nova\s+tentativa\s+de\s+intima[cç][aã]o",
    r"intime-?se\s+a\s+parte\s+autora\s+para\s+requer",
    r"intime-?se\s+a\s+parte\s+(?:autora|exequente)\s+.{0,60}requer",
    r"parte\s+autora\s+intimada\s+.{0,60}requer",
]

PADROES_TENTATIVA_FRUSTRADA = [
    r"indefiro.*cita[cç][aã]o",
    r"cita[cç][aã]o\s+por\s+whatsapp",
    r"cita[cç][aã]o\s+por\s+edital",
    r"intima[cç][aã]o\s+por\s+edital",
    r"certificar\s+o\s+cumprimento\s+da\s+dilig[êe]ncia",
    r"prazo\s+de\s+48\s+.{0,10}horas",
]

PADROES_NEGATIVOS_FORTES = [
    r"liminarmente\s+a\s+medida\s+postulada",
    r"defiro\s+liminarmente",
    r"expe[cç]a-?se\s+mandado",
    r"ve[ií]culo\s+apreendido",
    r"ciente\s+do\s+cumprimento\s+do\s+mandado",
    r"r[eé]u\s+citado",
    r"citado\s+pessoalmente",
    r"cumprimento\s+positivo",
    r"mandado\s+cumprido",
]


# =========================================================
# FUNÇÕES COMUNS
# =========================================================

def extrair_texto_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    partes = []
    for page in reader.pages:
        try:
            partes.append(page.extract_text() or "")
        except Exception:
            partes.append("")
    texto = "\n".join(partes)
    texto = texto.replace("\x00", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n+", "\n", texto)
    return texto.strip()


def badge_classificacao(cls: str, confianca: str):
    if "PRECISA DE NOVO ENDEREÇO" in cls and "NÃO" not in cls:
        st.warning(f"[!] {cls}")
    elif "NÃO PRECISA" in cls:
        st.success(f"[+] {cls}")
    else:
        st.info(f"[?] {cls}")
    st.caption(f"Confiança: **{confianca.upper()}**")


# =========================================================
# MÉTODO 1 — REGEX
# =========================================================

def encontrar(texto: str, padroes: List[str]) -> List[str]:
    return [p for p in padroes if re.search(p, texto, flags=re.IGNORECASE | re.DOTALL)]


def classificar_regex(texto: str) -> Dict:
    falha_forte         = encontrar(texto, PADROES_FALHA_FORTE)
    motivo_localizacao  = encontrar(texto, PADROES_MOTIVO_LOCALIZACAO)
    providencia         = encontrar(texto, PADROES_PROVIDENCIA)
    tentativa_frustrada = encontrar(texto, PADROES_TENTATIVA_FRUSTRADA)
    negativos_fortes    = encontrar(texto, PADROES_NEGATIVOS_FORTES)

    score = 0
    if falha_forte:         score += 5
    if motivo_localizacao:  score += 4
    if providencia:         score += 3
    if tentativa_frustrada: score += 3
    if negativos_fortes and not falha_forte and not motivo_localizacao and not tentativa_frustrada:
        score -= 4

    if falha_forte and motivo_localizacao:
        cls, conf = "PROVAVELMENTE PRECISA DE NOVO ENDEREÇO", "alta"
    elif falha_forte:
        cls, conf = "PROVAVELMENTE PRECISA DE NOVO ENDEREÇO", "alta"
    elif tentativa_frustrada and providencia:
        cls, conf = "PROVAVELMENTE PRECISA DE NOVO ENDEREÇO", "média"
    elif providencia and motivo_localizacao:
        cls, conf = "PROVAVELMENTE PRECISA DE NOVO ENDEREÇO", "média"
    elif providencia and score >= 3 and not negativos_fortes:
        cls, conf = "PROVAVELMENTE PRECISA DE NOVO ENDEREÇO", "média"
    elif score >= 5:
        cls, conf = "PROVAVELMENTE PRECISA DE NOVO ENDEREÇO", "média"
    elif negativos_fortes:
        cls, conf = "PROVAVELMENTE NÃO PRECISA DE NOVO ENDEREÇO", "média"
    else:
        cls, conf = "INDETERMINADO", "baixa"

    padroes_todos = (
        PADROES_FALHA_FORTE + PADROES_MOTIVO_LOCALIZACAO
        + PADROES_PROVIDENCIA + PADROES_TENTATIVA_FRUSTRADA
    )
    blocos = re.split(r"\n|(?<=[\.\!\?])\s+", texto)
    trechos, vistos = [], set()
    for bloco in blocos:
        t = bloco.strip()
        if not t:
            continue
        for p in padroes_todos:
            if re.search(p, t, flags=re.IGNORECASE | re.DOTALL):
                key = t.lower()
                if key not in vistos:
                    vistos.add(key)
                    trechos.append(t)
                break
    trechos = trechos[:12]

    return {
        "classificacao": cls,
        "confianca": conf,
        "score": score,
        "falha_forte": falha_forte,
        "motivo_localizacao": motivo_localizacao,
        "providencia": providencia,
        "tentativa_frustrada": tentativa_frustrada,
        "negativos_fortes": negativos_fortes,
        "trechos": trechos,
    }


def render_regex(resultado: Dict):
    badge_classificacao(resultado["classificacao"], resultado["confianca"])
    st.metric("Score", resultado["score"])

    st.markdown("**Sinais encontrados:**")
    sinais = [
        ("[X] Falha de citação/mandado",    resultado["falha_forte"]),
        ("[!] Motivo de localização inválida", resultado["motivo_localizacao"]),
        ("[*] Pedido de providência",        resultado["providencia"]),
        ("[-] Tentativa frustrada",          resultado["tentativa_frustrada"]),
        ("[+] Sinal de andamento normal",    resultado["negativos_fortes"]),
    ]
    algum = False
    for label, lista in sinais:
        if lista:
            algum = True
            st.markdown(f"- **{label}:** detectado ({len(lista)} padrão/padrões)")
    if not algum:
        st.write("Nenhum sinal identificado.")

    if resultado["trechos"]:
        st.markdown("**Trechos relevantes:**")
        for t in resultado["trechos"]:
            st.write(f"- {t}")


# =========================================================
# MÉTODO 2 — ANTHROPIC CLAUDE API
# =========================================================

SYSTEM_PROMPT = """Você é um assistente jurídico especializado em processos judiciais brasileiros.
Sua tarefa é analisar o texto de uma publicação judicial e determinar se o advogado precisará
informar um novo endereço para localizar o réu/citando.

Retorne SOMENTE um objeto JSON válido, sem markdown, sem texto fora do JSON,
exatamente neste formato:
{
  "classificacao": "PRECISA DE NOVO ENDEREÇO" | "NÃO PRECISA DE NOVO ENDEREÇO" | "INDETERMINADO",
  "confianca": "alta" | "média" | "baixa",
  "motivo": "explicação curta em português do raciocínio utilizado",
  "sinais_encontrados": ["sinal 1", "sinal 2"],
  "trechos_relevantes": ["trecho literal do documento 1", "trecho literal 2"]
}

Critérios para PRECISA DE NOVO ENDEREÇO:
- Mandado devolvido, juntado ou retornado sem cumprimento
- Certidão negativa do oficial de justiça
- AR (aviso de recebimento) assinado por terceiro que não o réu
- Réu não encontrado, não localizado, desconhecido no endereço
- Imóvel desocupado, vazio, abandonado ou fechado
- Parte intimada para informar novo endereço ou requerer prosseguimento após falha de citação
- Diligência infrutífera, sem êxito ou não cumprida
- Qualquer indicação de que a citação/intimação não chegou ao destinatário correto

Critérios para NÃO PRECISA DE NOVO ENDEREÇO:
- Réu citado ou intimado pessoalmente com sucesso
- Mandado cumprido com êxito
- Processo em andamento normal sem nenhuma falha de localização
- Concessão de liminar ou expedição de mandado sem relação com falha de citação

Na dúvida, prefira classificar como PRECISA DE NOVO ENDEREÇO."""


def classificar_claude(texto: str, api_key: str, modelo: str) -> Dict:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    # Trunca o texto para não exceder contexto
    texto_truncado = texto[:6000] + ("\n[... texto truncado ...]" if len(texto) > 6000 else "")

    message = client.messages.create(
        model=modelo,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Texto da publicação judicial:\n\n{texto_truncado}"
            }
        ],
    )

    raw = message.content[0].text

    # Remove markdown caso o modelo inclua ```json ... ```
    raw_clean = re.sub(r"```(?:json)?|```", "", raw).strip()
    resultado = json.loads(raw_clean)

    # Garante campos mínimos
    resultado.setdefault("classificacao", "INDETERMINADO")
    resultado.setdefault("confianca", "baixa")
    resultado.setdefault("motivo", "")
    resultado.setdefault("sinais_encontrados", [])
    resultado.setdefault("trechos_relevantes", [])

    # Tokens consumidos
    resultado["tokens_entrada"] = message.usage.input_tokens
    resultado["tokens_saida"]   = message.usage.output_tokens

    return resultado


def render_claude(resultado: Dict):
    badge_classificacao(resultado["classificacao"], resultado["confianca"])

    st.markdown("**Raciocínio do modelo:**")
    st.info(resultado.get("motivo", "—"))

    if resultado.get("sinais_encontrados"):
        st.markdown("**Sinais identificados:**")
        for s in resultado["sinais_encontrados"]:
            st.write(f"- {s}")

    if resultado.get("trechos_relevantes"):
        st.markdown("**Trechos relevantes:**")
        for t in resultado["trechos_relevantes"]:
            st.write(f"- *{t}*")

    ti = resultado.get("tokens_entrada", 0)
    ts = resultado.get("tokens_saida", 0)
    if ti or ts:
        st.caption(f"Tokens: {ti} entrada + {ts} saída = {ti + ts} total")


# =========================================================
# CONFIGURAÇÃO
# =========================================================

# Tenta carregar API key do Streamlit secrets ou .env
try:
    anthropic_key = st.secrets["api_key_anthropic"]
except:
    anthropic_key = os.getenv("api_key_anthropic", "")

modelo_claude = "claude-haiku-4-5-20251001"


# =========================================================
# APP PRINCIPAL
# =========================================================

st.title("Detector de Novo Endereço")
st.caption("Compara dois métodos em paralelo: **Método 1** vs **Método 2**")

arquivo = st.file_uploader("Envie um PDF de publicação judicial", type=["pdf"])

if arquivo is not None:
    with st.spinner("Extraindo texto do PDF..."):
        texto = extrair_texto_pdf(arquivo.read())

    if not texto:
        st.error("Não consegui extrair texto do PDF. Verifique se não é um PDF escaneado sem OCR.")
        st.stop()

    col_regex, col_ai = st.columns(2, gap="large")

    # — Coluna Regex —
    with col_regex:
        st.subheader("Método 1")
        with st.spinner("Analisando..."):
            res_regex = classificar_regex(texto)
        render_regex(res_regex)

    # — Coluna Claude —
    with col_ai:
        st.subheader("Método 2")
        if not anthropic_key:
            st.warning("Configure a API Key da Anthropic no arquivo .env para usar este método.")
        else:
            with st.spinner(f"Consultando {modelo_claude}..."):
                try:
                    res_ai = classificar_claude(texto, anthropic_key, modelo_claude)
                    render_claude(res_ai)
                except Exception as e:
                    st.error(f"Erro na API Anthropic: {e}")

    # — Comparação —
    if anthropic_key and "res_ai" in dir():
        st.divider()
        st.subheader("Comparação")

        cls_regex = res_regex["classificacao"]
        cls_ai    = res_ai.get("classificacao", "—")

        precisa_regex = "PRECISA" in cls_regex and "NÃO" not in cls_regex
        precisa_ai    = "PRECISA" in cls_ai    and "NÃO" not in cls_ai
        nao_regex     = "NÃO PRECISA" in cls_regex
        nao_ai        = "NÃO PRECISA" in cls_ai
        ind_regex     = cls_regex == "INDETERMINADO"
        ind_ai        = cls_ai   == "INDETERMINADO"

        concordam = (
            (precisa_regex and precisa_ai)
            or (nao_regex and nao_ai)
            or (ind_regex and ind_ai)
        )

        if concordam:
            st.success(f"[+] **Os dois métodos concordam:** {cls_ai}")
        else:
            st.error(
                f"[X] **Divergência detectada!**\n\n"
                f"- Método 1: **{cls_regex}** (confiança: {res_regex['confianca']})\n"
                f"- Método 2: **{cls_ai}** (confiança: {res_ai.get('confianca', '—')})\n\n"
                f"Motivo do Método 2: _{res_ai.get('motivo', '—')}_"
            )

    # — Texto bruto —
    with st.expander("Texto extraído do PDF"):
        st.text_area("", texto, height=400)
