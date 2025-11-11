import streamlit as st
import pandas as pd
import os
import datetime
import json
import base64
from bs4 import BeautifulSoup
hola estoy provando si esto funcionas
# Importaciones para la integración con Google Drive
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="JCT - Panel de Entrenador",
    page_icon="💪",
    layout="wide"
)

# --- CONSTANTES ---
CREDENTIALS_FILE = "credentials.json"
MAIN_FOLDER_NAME = "JCT Entrenamientos"
DRAFT_SUFFIX = ".draft.json"

# --- LÓGICA DE GOOGLE DRIVE (MODIFICADA Y AMPLIADA) ---

try:
    # Mantenemos tu método de configuración de secrets
    GOOGLE_AUTH_SETTINGS = {
        "client_config_backend": "settings",
        "client_config": {
            "web": {
                "client_id": st.secrets["client_id"],
                "client_secret": st.secrets["client_secret"],
                "auth_uri": st.secrets["auth_uri"],
                "token_uri": st.secrets["token_uri"],
                "auth_provider_x509_cert_url": st.secrets["auth_provider_x509_cert_url"],
                "redirect_uris": st.secrets["redirect_uris"]
            }
        },
        "oauth_scope": ["https://www.googleapis.com/auth/drive"]
    }
except KeyError as e:
    st.error(f"Error: Falta un secreto esencial en la configuración de tu app: {e}")
    st.info("Por favor, ve a 'Manage app' -> 'Secrets' y asegúrate de que todas las claves de Google (client_id, client_secret, etc.) estén definidas.")
    st.stop()

def authenticate_gdrive():
    """Realiza la autenticación con Google Drive usando el flujo OAuth 2.0."""
    try:
        gauth = GoogleAuth(settings=GOOGLE_AUTH_SETTINGS)
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

def get_or_create_folder(drive, folder_name, parent_id=None):
    """Busca una carpeta por nombre. Si no existe, la crea. Devuelve el ID de la carpeta."""
    query = f"title='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    file_list = drive.ListFile({'q': query}).GetList()
    if file_list:
        return file_list[0]['id']
    else:
        folder_metadata = {'title': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
        if parent_id:
            folder_metadata['parents'] = [{'id': parent_id}]
        folder = drive.CreateFile(folder_metadata)
        folder.Upload()
        return folder['id']

def list_clients(drive):
    """Devuelve una lista con los nombres de las carpetas de clientes."""
    main_folder_id = get_or_create_folder(drive, MAIN_FOLDER_NAME)
    query = f"'{main_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    client_folders = drive.ListFile({'q': query}).GetList()
    return sorted([folder['title'] for folder in client_folders])

def create_client(drive, client_name):
    """Crea una nueva carpeta de cliente."""
    main_folder_id = get_or_create_folder(drive, MAIN_FOLDER_NAME)
    get_or_create_folder(drive, client_name, parent_id=main_folder_id)

def list_trainings(drive, client_name):
    """Devuelve dos listas: una de borradores (.json) y otra de entrenamientos finalizados (.html)."""
    main_folder_id = get_or_create_folder(drive, MAIN_FOLDER_NAME)
    client_folder_id = get_or_create_folder(drive, client_name, parent_id=main_folder_id)

    file_list = drive.ListFile({'q': f"'{client_folder_id}' in parents and trashed=false"}).GetList()
    drafts, finalized = [], []
    for f in file_list:
        if f['title'].endswith(DRAFT_SUFFIX):
            drafts.append(f['title'].replace(DRAFT_SUFFIX, ''))
        elif f['mimeType'] == 'text/html' or f['title'].endswith('.html'):
            finalized.append({'title': f['title'], 'alternateLink': f['alternateLink']})
    return sorted(drafts), sorted(finalized, key=lambda x: x['title'], reverse=True)

def get_draft_data(drive, client_name, draft_name):
    """Obtiene el contenido de un archivo de borrador y lo devuelve como un diccionario."""
    main_folder_id = get_or_create_folder(drive, MAIN_FOLDER_NAME)
    client_folder_id = get_or_create_folder(drive, client_name, parent_id=main_folder_id)
    file_name = f"{draft_name}{DRAFT_SUFFIX}"

    file_list = drive.ListFile({'q': f"title='{file_name}' and '{client_folder_id}' in parents and trashed=false"}).GetList()
    return json.loads(file_list[0].GetContentString()) if file_list else {}

def save_draft(drive, client_name, draft_name, data):
    """Guarda o actualiza un archivo de borrador (.json) en la carpeta del cliente."""
    main_folder_id = get_or_create_folder(drive, MAIN_FOLDER_NAME)
    client_folder_id = get_or_create_folder(drive, client_name, parent_id=main_folder_id)
    file_name = f"{draft_name}{DRAFT_SUFFIX}"

    file_list = drive.ListFile({'q': f"title='{file_name}' and '{client_folder_id}' in parents and trashed=false"}).GetList()
    draft_file = file_list[0] if file_list else drive.CreateFile({'title': file_name, 'parents': [{'id': client_folder_id}]})
    draft_file.SetContentString(json.dumps(data, indent=4))
    draft_file.Upload()

def finalize_training(drive, client_name, training_name, html_content):
    """Sube el archivo HTML final y elimina el borrador correspondiente."""
    main_folder_id = get_or_create_folder(drive, MAIN_FOLDER_NAME)
    client_folder_id = get_or_create_folder(drive, client_name, parent_id=main_folder_id)

    html_file_name = f"{training_name}.html"
    html_file = drive.CreateFile({'title': html_file_name, 'parents': [{'id': client_folder_id}], 'mimeType': 'text/html'})
    html_file.SetContentString(html_content, 'utf-8')
    html_file.Upload()

    draft_file_name = f"{training_name}{DRAFT_SUFFIX}"
    file_list = drive.ListFile({'q': f"title='{draft_file_name}' and '{client_folder_id}' in parents and trashed=false"}).GetList()
    if file_list:
        file_list[0].Delete()
    return html_file['alternateLink']

# --- LÓGICA DE GENERACIÓN DE HTML ---
def generate_html_from_template(data, client_name):
    """Rellena la plantilla HTML con los datos del entrenamiento."""
    try:
        with open("template.html", "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        # Función para reemplazar texto de forma segura
        def replace_content(tag_id, content):
            element = soup.find(id=tag_id)
            if element:
                element.string = content

        # Rellenar datos
        replace_content('client_name', client_name)
        replace_content('training_day', data.get('dia_semana', 'DÍA'))
        replace_content('training_date', datetime.datetime.fromisoformat(data['fecha_creacion']).strftime('%Y·%m·%d'))

        # Rellenar áreas de texto, convirtiendo saltos de línea a <br>
        for key in ['objetivo_sesion', 'warmup_general', 'specific_warmup', 'fuerza', 'trabajo_especifico', 'conditioning', 'anotaciones_coach']:
            element = soup.find(id=key)
            if element:
                element.clear() # Limpia el contenido placeholder
                element.append(BeautifulSoup(data.get(key, '').replace('\n', '<br/>'), 'html.parser'))
        
        return str(soup)
    except FileNotFoundError:
        st.error("Error: No se encontró el archivo 'template.html'. Asegúrate de que está en la misma carpeta que app.py.")
        return None
    except Exception as e:
        st.error(f"Error al generar el HTML: {e}")
        return None

# --- GESTIÓN DE NAVEGACIÓN ---
if 'page' not in st.session_state:
    st.session_state.page = 'client_selection'

def set_page(page_name):
    st.session_state.page = page_name

# --- DEFINICIÓN DE PÁGINAS (NUEVA ESTRUCTURA) ---

def page_client_selection():
    """Página para ver la lista de clientes (carpetas) y crear nuevos."""
    st.title("Panel de Entrenador - Clientes en Google Drive")
    st.markdown("---")

    with st.spinner("Cargando clientes desde Google Drive..."):
        clients = list_clients(st.session_state.drive)

    if not clients:
        st.info("Aún no has creado ningún cliente. Los clientes son carpetas en Google Drive.")
    else:
        st.subheader("Selecciona un cliente:")
        cols = st.columns(4)
        for i, client in enumerate(clients):
            if cols[i % 4].button(client, key=f"client_{client}", use_container_width=True):
                st.session_state.selected_client = client
                set_page('training_list')
                st.rerun()

    st.markdown("---")
    with st.expander("➕ Crear un nuevo cliente"):
        with st.form("new_client_form"):
            new_client_name = st.text_input("Nombre del nuevo cliente (se creará una carpeta):")
            if st.form_submit_button("Crear Cliente"):
                if new_client_name and new_client_name not in clients:
                    with st.spinner(f"Creando carpeta para '{new_client_name}'..."):
                        create_client(st.session_state.drive, new_client_name)
                    st.success(f"¡Cliente '{new_client_name}' creado!")
                    st.rerun()
                else:
                    st.warning("El nombre no puede estar vacío o ya existe.")

def page_training_list():
    """Página para ver los entrenamientos (borradores y finalizados) de un cliente."""
    client_name = st.session_state.selected_client
    
    if st.button("⬅️ Volver a la lista de clientes"):
        set_page('client_selection')
        st.rerun()

    st.title(f"Entrenamientos para: {client_name}")

    with st.spinner("Cargando entrenamientos..."):
        drafts, finalized = list_trainings(st.session_state.drive, client_name)

    if st.button("➕ Crear Nuevo Entrenamiento", type="primary", use_container_width=True):
        st.session_state.training_name = f"Entrenamiento {datetime.date.today().isoformat()}"
        st.session_state.training_data = {'fecha_creacion': datetime.date.today().isoformat()}
        set_page('training_editor')
        st.rerun()

    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("✏️ Borradores (A medias)")
        if not drafts:
            st.info("No hay borradores.")
        else:
            for draft_name in drafts:
                if st.button(f"Continuar '{draft_name}'", key=f"edit_{draft_name}", use_container_width=True):
                    with st.spinner("Cargando borrador..."):
                        st.session_state.training_data = get_draft_data(st.session_state.drive, client_name, draft_name)
                        st.session_state.training_name = draft_name
                    set_page('training_editor')
                    st.rerun()
    
    with col2:
        st.subheader("✅ Entrenamientos Finalizados")
        if not finalized:
            st.info("No hay entrenamientos finalizados.")
        else:
            for final_file in finalized:
                st.markdown(f"📄 [{final_file['title']}]({final_file['alternateLink']})")

def page_training_editor():
    """Página para crear o editar un entrenamiento."""
    client_name = st.session_state.selected_client
    
    if st.button(f"⬅️ Volver a los entrenamientos de {client_name}"):
        set_page('training_list')
        st.rerun()

    st.title(f"Editando entrenamiento para: {client_name}")
    data = st.session_state.get('training_data', {})

    st.session_state.training_name = st.text_input("Nombre del archivo (sin extensión):", st.session_state.get('training_name', ''))
    
    c1, c2 = st.columns(2)
    current_date = datetime.datetime.fromisoformat(data.get('fecha_creacion', datetime.date.today().isoformat())).date()
    data['fecha_creacion'] = c1.date_input("Fecha de la sesión", value=current_date).isoformat()
    data['dia_semana'] = c2.text_input("Día (Ej: LUNES 6)", value=data.get('dia_semana', ''))

    st.markdown("---")
    data['objetivo_sesion'] = st.text_area("🎯 Objetivo", value=data.get('objetivo_sesion', ''), height=100)
    data['warmup_general'] = st.text_area("🔥 Warm-Up General", value=data.get('warmup_general', ''), height=150)
    data['specific_warmup'] = st.text_area("✨ Specific Warm-Up", value=data.get('specific_warmup', ''), height=100)
    data['fuerza'] = st.text_area("🏋️ Fuerza", value=data.get('fuerza', ''), height=150)
    data['trabajo_especifico'] = st.text_area("⚡ Trabajo Específico", value=data.get('trabajo_especifico', ''), height=150)
    data['conditioning'] = st.text_area("🏃 Conditioning", value=data.get('conditioning', ''), height=150)
    data['anotaciones_coach'] = st.text_area("📝 Anotaciones", value=data.get('anotaciones_coach', ''), height=100)

    st.session_state.training_data = data
    st.markdown("---")

    b1, b2 = st.columns([1, 2])
    if b1.button("💾 Guardar Borrador", use_container_width=True):
        if st.session_state.training_name:
            with st.spinner("Guardando borrador en Google Drive..."):
                save_draft(st.session_state.drive, client_name, st.session_state.training_name, data)
            st.toast("¡Borrador guardado!", icon="💾")
        else:
            st.warning("El nombre del archivo no puede estar vacío.")

    if b2.button("✅ Finalizar y Generar HTML", type="primary", use_container_width=True):
        if st.session_state.training_name:
            final_html = generate_html_from_template(data, client_name)
            if final_html:
                with st.spinner("Subiendo HTML a Google Drive..."):
                    file_link = finalize_training(st.session_state.drive, client_name, st.session_state.training_name, final_html)
                
                st.success(f"¡Entrenamiento finalizado! [Ver en Google Drive]({file_link})")
                b64 = base64.b64encode(final_html.encode('utf-8')).decode()
                st.markdown(f'<a href="data:file/html;base64,{b64}" download="{st.session_state.training_name}.html" class="button">📥 Descargar HTML</a>', unsafe_allow_html=True)
                st.balloons()
        else:
            st.warning("El nombre del archivo no puede estar vacío para finalizar.")

# --- ROUTER PRINCIPAL DE LA APLICACIÓN ---
def main():
    st.sidebar.title("JCT Training Panel")
    # Autenticamos al inicio y guardamos el objeto 'drive' en la sesión
    if 'drive' not in st.session_state:
        st.session_state.drive = authenticate_gdrive()
    
    # Si la autenticación es exitosa, mostramos la app
    if st.session_state.drive:
        pages = {
            'client_selection': page_client_selection,
            'training_list': page_training_list,
            'training_editor': page_training_editor,
        }
        # Ejecuta la función de la página actual
        pages.get(st.session_state.page, page_client_selection)()

if __name__ == "__main__":
    main()
