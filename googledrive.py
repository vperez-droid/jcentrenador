import streamlit as st
from PIL import Image
import sqlite3
import pandas as pd
import os
from passlib.context import CryptContext
import datetime
import json

# Importaciones para la integración con Google Drive
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="JCT - Panel de Entrenador", page_icon="💪", layout="wide")

# --- INICIALIZACIÓN DE SEGURIDAD Y CONSTANTES ---
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "jct_main.db")
CREDENTIALS_FILE = "credentials.json"

# --- LÓGICA DE GOOGLE DRIVE (INTEGRADA) ---

# Configuración de autenticación de Google Drive usando los secrets de Streamlit
GOOGLE_AUTH_SETTINGS = {
    "client_config_backend": "settings",
    "client_config": {
        "web": {
            "client_id": st.secrets.google_credentials.client_id,
            "client_secret": st.secrets.google_credentials.client_secret,
            "project_id": st.secrets.google_credentials.project_id,
            "auth_uri": st.secrets.google_credentials.auth_uri,
            "token_uri": st.secrets.google_credentials.token_uri,
            "auth_provider_x509_cert_url": st.secrets.google_credentials.auth_provider_x509_cert_url,
            "redirect_uris": st.secrets.google_credentials.redirect_uris
        }
    },
    "oauth_scope": ["https://www.googleapis.com/auth/drive"]
}

def authenticate_gdrive():
    """Realiza la autenticación con Google Drive usando el flujo OAuth 2.0."""
    try:
        gauth = GoogleAuth(settings=GOOGLE_AUTH_SETTINGS)
        
        # Cargar credenciales si el archivo existe (para sesiones posteriores)
        if os.path.exists(CREDENTIALS_FILE):
            gauth.LoadCredentialsFile(CREDENTIALS_FILE)

        if gauth.credentials is None:
            st.warning("Se necesita autorización para acceder a Google Drive.")
            auth_url = gauth.GetAuthUrl()
            st.markdown(f"**1. Haz clic aquí para autorizar:** [Enlace de Autorización de Google]({auth_url})", unsafe_allow_html=True)
            
            code = st.text_input("2. Pega el código de autorización que recibiste aquí:")
            if st.button("Autorizar App"):
                if code:
                    gauth.Auth(code)
                    gauth.SaveCredentialsFile(CREDENTIALS_FILE)
                    st.success("¡Autorización exitosa! La página se refrescará para continuar.")
                    st.rerun()
                else:
                    st.error("El código no puede estar vacío.")
            st.stop()
            
        elif gauth.access_token_expired:
            gauth.Refresh()
            gauth.SaveCredentialsFile(CREDENTIALS_FILE)
        else:
            gauth.Authorize()
            
        return GoogleDrive(gauth)
        
    except Exception as e:
        st.error(f"Error en la autenticación con Google Drive: {e}")
        st.info("Verifica la configuración de 'Secrets' en Streamlit Cloud.")
        return None

def create_training_file_in_drive(drive, client_name, training_data):
    """Crea una carpeta para el cliente y guarda el entrenamiento como un archivo .txt."""
    try:
        folder_list = drive.ListFile({'q': "title='JCT Entrenamientos' and mimeType='application/vnd.google-apps.folder' and trashed=false"}).GetList()
        main_folder_id = folder_list[0]['id'] if folder_list else drive.CreateFile({'title': 'JCT Entrenamientos', 'mimeType': 'application/vnd.google-apps.folder'}).Upload()['id']

        client_folder_list = drive.ListFile({'q': f"title='{client_name}' and '{main_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"}).GetList()
        client_folder_id = client_folder_list[0]['id'] if client_folder_list else drive.CreateFile({'title': client_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [{'id': main_folder_id}]}).Upload()['id']

        file_name = f"Entrenamiento_{training_data['fecha_creacion']}.txt"
        content = f"""# Entrenamiento para: {client_name}
# Fecha: {training_data['fecha_creacion']} ({training_data.get('dia_semana', '')})
\n## 🎯 Objetivo de la Sesión\n{training_data.get('objetivo_sesion', 'N/A')}
\n## 🔥 Warm-Up General\n{training_data.get('warmup_general', 'N/A')}
\n## ✨ Specific Warm-Up\n{training_data.get('specific_warmup', 'N/A')}
\n## 🏋️ Fuerza / Weightlifting\n{training_data.get('fuerza', 'N/A')}
\n## ⚡ Trabajo Específico\n{training_data.get('trabajo_especifico', 'N/A')}
\n## 🏃 Conditioning\n{training_data.get('conditioning', 'N/A')}
\n## 📝 Anotaciones del Coach\n{training_data.get('anotaciones_coach', 'N/A')}
"""
        training_file = drive.CreateFile({'title': file_name, 'parents': [{'id': client_folder_id}], 'mimeType': 'text/plain'})
        training_file.SetContentString(content)
        training_file.Upload()
        return training_file['alternateLink']

    except Exception as e:
        st.error(f"Error al crear el archivo en Google Drive: {e}")
        return None

# --- GESTIÓN DE LA BASE DE DATOS (SQLite) ---
def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, nombre TEXT, objetivo TEXT, username TEXT UNIQUE, password_hash TEXT, fecha_registro TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS entrenamientos (id INTEGER PRIMARY KEY, user_id INTEGER, fecha_creacion TEXT, dia_semana TEXT, objetivo_sesion TEXT, warmup_general TEXT, specific_warmup TEXT, fuerza TEXT, trabajo_especifico TEXT, conditioning TEXT, anotaciones_coach TEXT, FOREIGN KEY (user_id) REFERENCES users (id))')
    cursor.execute('CREATE TABLE IF NOT EXISTS drafts (user_id INTEGER PRIMARY KEY, draft_data TEXT, last_updated TEXT, FOREIGN KEY (user_id) REFERENCES users (id))')
    
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        sample_users = [("Ana García", "Pérdida de peso", "anagarcia", pwd_context.hash("ana2025"), "2025-09-15"), ("Carlos Sánchez", "Ganancia muscular", "csanchez", pwd_context.hash("carlosfit"), "2025-10-05")]
        cursor.executemany("INSERT INTO users (nombre, objetivo, username, password_hash, fecha_registro) VALUES (?, ?, ?, ?, ?)", sample_users)
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# --- LÓGICA DE BORRADORES ---
def get_draft(user_id):
    conn = get_db_connection()
    draft = conn.execute("SELECT draft_data FROM drafts WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return json.loads(draft['draft_data']) if draft else None

def save_draft(user_id, data):
    conn = get_db_connection()
    conn.execute("REPLACE INTO drafts (user_id, draft_data, last_updated) VALUES (?, ?, ?)", (user_id, json.dumps(data), datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

def delete_draft(user_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM drafts WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# --- GESTIÓN DE NAVEGACIÓN ---
if 'page' not in st.session_state:
    st.session_state.page = 'inicio'

def set_page(page):
    st.session_state.page = page

# --- DEFINICIÓN DE PÁGINAS ---
def page_inicio():
    # ... (código de la página de inicio sin cambios)
    pass

def page_registrar():
    # ... (código de la página de registro sin cambios)
    pass

def page_ver_clientes():
    # ... (código de la página de ver clientes sin cambios)
    pass
    
def page_crear_entrenamiento():
    if st.button("⬅️ Volver al inicio"):
        for key in list(st.session_state.keys()):
            if key.startswith('wizard_'): del st.session_state[key]
        set_page('inicio'); st.rerun()

    st.title("💪 Creador de Sesiones de Entrenamiento")

    if 'wizard_step' not in st.session_state:
        st.session_state.wizard_step = 1

    if st.session_state.wizard_step == 1:
        st.subheader("Paso 1: Cliente y Fecha")
        conn = get_db_connection()
        clientes = pd.read_sql_query("SELECT id, nombre FROM users", conn)
        conn.close()
        if clientes.empty: st.warning("No hay clientes registrados."); return

        cliente_id = st.selectbox("Selecciona el cliente", clientes['id'], format_func=lambda x: clientes[clientes['id'] == x]['nombre'].iloc[0])
        
        draft = get_draft(cliente_id)
        if draft:
            st.info("Se ha encontrado un borrador para este cliente.")
            c1, c2 = st.columns(2)
            if c1.button("Continuar borrador", use_container_width=True):
                st.session_state.wizard_data = draft; st.session_state.wizard_step = 2; st.rerun()
            if c2.button("Empezar de cero", type="primary", use_container_width=True):
                delete_draft(cliente_id); st.session_state.wizard_data = {}; st.rerun()
        
        if 'wizard_data' not in st.session_state:
            st.session_state.wizard_data = {}
        
        data = st.session_state.wizard_data
        data['user_id'] = cliente_id
        data['client_name'] = clientes[clientes['id'] == cliente_id]['nombre'].iloc[0]
        
        try: date_val = datetime.datetime.fromisoformat(data['fecha_creacion']).date()
        except: date_val = datetime.date.today()
        
        data['fecha_creacion'] = st.date_input("Fecha de la sesión", value=date_val).isoformat()
        data['dia_semana'] = st.text_input("Día (Ej: LUNES 6)", value=data.get('dia_semana', ''))
        
        if st.button("Siguiente ➡️"):
            st.session_state.wizard_step = 2; st.rerun()

    elif st.session_state.wizard_step == 2:
        data = st.session_state.wizard_data
        st.subheader(f"Paso 2: Contenido para {data.get('client_name', '')}")
        
        data['objetivo_sesion'] = st.text_area("🎯 Objetivo", value=data.get('objetivo_sesion', ''), height=100)
        data['warmup_general'] = st.text_area("🔥 Warm-Up General", value=data.get('warmup_general', ''), height=150)
        data['specific_warmup'] = st.text_area("✨ Specific Warm-Up", value=data.get('specific_warmup', ''), height=100)
        data['fuerza'] = st.text_area("🏋️ Fuerza", value=data.get('fuerza', ''), height=150)
        data['trabajo_especifico'] = st.text_area("⚡ Trabajo Específico", value=data.get('trabajo_especifico', ''), height=150)
        data['conditioning'] = st.text_area("🏃 Conditioning", value=data.get('conditioning', ''), height=150)
        data['anotaciones_coach'] = st.text_area("📝 Anotaciones", value=data.get('anotaciones_coach', ''), height=100)

        c1, c2, c3 = st.columns(3)
        if c1.button("⬅️ Anterior"): st.session_state.wizard_step = 1; st.rerun()
        if c2.button("💾 Guardar Borrador"): save_draft(data['user_id'], data); st.toast("¡Borrador guardado!")
        if c3.button("✅ Finalizar y Guardar en Drive", type="primary"):
            try:
                conn = get_db_connection()
                conn.execute("INSERT INTO entrenamientos (user_id, fecha_creacion, dia_semana, objetivo_sesion, warmup_general, specific_warmup, fuerza, trabajo_especifico, conditioning, anotaciones_coach) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (data['user_id'], data['fecha_creacion'], data.get('dia_semana'), data.get('objetivo_sesion'), data.get('warmup_general'), data.get('specific_warmup'), data.get('fuerza'), data.get('trabajo_especifico'), data.get('conditioning'), data.get('anotaciones_coach')))
                conn.commit(); conn.close()
                st.success("Entrenamiento guardado en la base de datos local.")

                with st.spinner("Conectando con Google Drive..."):
                    drive = authenticate_gdrive()
                    if drive:
                        link = create_training_file_in_drive(drive, data['client_name'], data)
                        if link: st.success(f"¡Entrenamiento guardado en Google Drive! [Ver archivo]({link})", icon="✅")
                
                delete_draft(data['user_id'])
                st.balloons()
                for key in list(st.session_state.keys()):
                    if key.startswith('wizard_'): del st.session_state[key]
                
            except Exception as e: st.error(f"Error al guardar: {e}")

def page_centro_control():
    # ... (código del centro de control sin cambios)
    pass

# --- ROUTER PRINCIPAL DE LA APLICACIÓN ---
def main():
    init_db() # Asegura que la DB siempre esté lista

    # El router decide qué página mostrar
    pages = {
        'inicio': page_inicio,
        'registrar': page_registrar,
        'ver_clientes': page_ver_clientes,
        'crear_entrenamiento': page_crear_entrenamiento,
        'centro_control': page_centro_control,
    }
    pages[st.session_state.page]()

if __name__ == "__main__":
    main()
