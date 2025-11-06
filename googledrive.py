# google_drive.py
import streamlit as st
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# Define la configuración de autenticación usando los secrets de Streamlit
SETTINGS = {
    "client_config_backend": "settings",
    "client_config": {
        "web": {
            "client_id": st.secrets.google_credentials.client_id,
            "client_secret": st.secrets.google_credentials.client_secret,
            "project_id": st.secrets.google_credentials.project_id,
            "auth_uri": st.secrets.google_credentials.auth_uri,
            "token_uri": st.secrets.google_credentials.token_uri,
            "auth_provider_x509_cert_url": st.secrets.google_credentials.auth_provider_x509_cert_url,
            "redirect_uris": st.secrets.google_credentials.redirect_uris,
            "javascript_origins": ["http://localhost:8501"]
        }
    },
    "oauth_scope": ["https://www.googleapis.com/auth/drive"],
    "get_refresh_token": True
}

def authenticate():
    """Realiza la autenticación con Google Drive."""
    try:
        gauth = GoogleAuth(settings=SETTINGS)
        # Intenta cargar credenciales guardadas
        gauth.LoadCredentialsFile("credentials.json")

        if gauth.credentials is None:
            # Autentica si no hay credenciales
            auth_url = gauth.GetAuthUrl()
            st.warning(f"Por favor, autoriza la app visitando esta URL: {auth_url}")
            code = st.text_input("Pega el código de autorización aquí:")
            if code:
                gauth.Auth(code)
                gauth.SaveCredentialsFile("credentials.json")
            else:
                st.stop()
        elif gauth.access_token_expired:
            # Refresca si han expirado
            gauth.Refresh()
            gauth.SaveCredentialsFile("credentials.json")
        else:
            # Inicializa el objeto si ya están autorizadas
            gauth.Authorize()
            
        return GoogleDrive(gauth)
    except Exception as e:
        st.error(f"Error durante la autenticación de Google Drive: {e}")
        st.error("Asegúrate de haber configurado correctamente los secrets en Streamlit Cloud.")
        return None

def create_training_file_in_drive(drive, client_name, training_data):
    """
    Crea una carpeta para el cliente si no existe y guarda el entrenamiento como un archivo de texto.
    """
    try:
        # 1. Buscar o crear la carpeta principal "JCT Entrenamientos"
        folder_list = drive.ListFile({'q': "title='JCT Entrenamientos' and mimeType='application/vnd.google-apps.folder' and trashed=false"}).GetList()
        if not folder_list:
            main_folder = drive.CreateFile({'title': 'JCT Entrenamientos', 'mimeType': 'application/vnd.google-apps.folder'})
            main_folder.Upload()
            main_folder_id = main_folder['id']
        else:
            main_folder_id = folder_list[0]['id']

        # 2. Buscar o crear la carpeta del cliente dentro de la principal
        client_folder_list = drive.ListFile({'q': f"title='{client_name}' and '{main_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"}).GetList()
        if not client_folder_list:
            client_folder = drive.CreateFile({'title': client_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [{'id': main_folder_id}]})
            client_folder.Upload()
            client_folder_id = client_folder['id']
        else:
            client_folder_id = client_folder_list[0]['id']

        # 3. Formatear el contenido del entrenamiento
        file_name = f"Entrenamiento_{training_data['fecha_creacion']}.txt"
        content = f"""
# Entrenamiento para: {client_name}
# Fecha: {training_data['fecha_creacion']} ({training_data['dia_semana']})

## 🎯 Objetivo de la Sesión
{training_data.get('objetivo_sesion', 'N/A')}

## 🔥 Warm-Up General
{training_data.get('warmup_general', 'N/A')}

##  स्पेसिफिक Warm-Up
{training_data.get('specific_warmup', 'N/A')}

## 🏋️ Fuerza / Weightlifting
{training_data.get('fuerza', 'N/A')}

## ⚡ Trabajo Específico
{training_data.get('trabajo_especifico', 'N/A')}

## 🏃 Conditioning
{training_data.get('conditioning', 'N/A')}

## 📝 Anotaciones del Coach
{training_data.get('anotaciones_coach', 'N/A')}
"""
        # 4. Crear y subir el archivo de texto
        training_file = drive.CreateFile({
            'title': file_name,
            'parents': [{'id': client_folder_id}],
            'mimeType': 'text/plain'
        })
        training_file.SetContentString(content)
        training_file.Upload()
        
        return training_file['alternateLink'] # Devuelve el enlace al archivo

    except Exception as e:
        st.error(f"Error al crear el archivo en Google Drive: {e}")
        return None
