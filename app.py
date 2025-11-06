import streamlit as st
from PIL import Image
import sqlite3
import pandas as pd
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="JCT - Panel de Entrenador",
    layout="wide"
)

# --- GESTIÓN DE LA BASE DE DATOS ---

# Define la ruta de la base de datos dentro de una carpeta 'database'
DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "jct_database.db")

def init_db():
    """Inicializa la base de datos y la tabla de clientes si no existen."""
    # Crea el directorio para la base de datos si no existe
    os.makedirs(DB_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Usamos "IF NOT EXISTS" para evitar errores si la tabla ya fue creada
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            telefono TEXT,
            objetivo TEXT
        );
    ''')
    conn.commit()
    conn.close()

# Inicializamos la base de datos al arrancar la app
init_db()

def get_db_connection():
    """Establece conexión con la base de datos."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# --- INTERFAZ DE LA APLICACIÓN ---

# Título y Logo
col1, col2, col3 = st.columns([2, 3, 2])
with col2:
    st.title("Panel de Entrenador - JCT")
    try:
        # La imagen se carga desde la carpeta 'assets'
        image = Image.open('assets/jct.jpeg')
        # Hemos cambiado 'use_column_width=True' por un ancho fijo en píxeles
        st.image(image, width=250) 
    except FileNotFoundError:
        st.error("No se encontró el logo 'assets/jct.jpeg'. Asegúrate de que la carpeta y el archivo existan.")

st.write("---")

# --- PESTAÑAS PRINCIPALES ---
tab1, tab2 = st.tabs(["👤 Registrar Nuevo Cliente", "📋 Ver Clientes Registrados"])

# --- Pestaña 1: Registrar Nuevo Cliente ---
with tab1:
    st.header("Formulario de Registro de Cliente")

    # Creamos un formulario para agrupar los campos y el botón
    with st.form("registro_cliente_form", clear_on_submit=True):
        st.subheader("Información Personal")
        nombre = st.text_input("Nombre completo del cliente *")
        email = st.text_input("Email del cliente *")
        telefono = st.text_input("Teléfono del cliente (Opcional)")

        st.subheader("Objetivo Principal")
        objetivo = st.selectbox("Selecciona el objetivo principal del cliente", [
            "Recomposición corporal", "Fuerza", "Pérdida de peso", "Ganancia muscular",
            "Rendimiento deportivo", "Salud postural / dolor", "Hábitos y salud general", "Otro"
        ], index=0)

        # Botón para enviar el formulario
        submitted = st.form_submit_button("✅ Registrar Cliente")

        if submitted:
            if not nombre or not email:
                st.warning("El nombre y el email son campos obligatorios.")
            else:
                try:
                    conn = get_db_connection()
                    conn.execute(
                        "INSERT INTO clientes (nombre, email, telefono, objetivo) VALUES (?, ?, ?, ?)",
                        (nombre, email, telefono, objetivo)
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"¡Cliente '{nombre}' registrado con éxito!")
                except sqlite3.IntegrityError:
                    st.error(f"El email '{email}' ya está registrado. Por favor, utiliza otro.")
                except Exception as e:
                    st.error(f"Ha ocurrido un error al registrar el cliente: {e}")

# --- Pestaña 2: Ver Clientes Registrados ---
with tab2:
    st.header("Lista de Clientes")

    try:
        conn = get_db_connection()
        # Leemos los datos de la tabla clientes y los cargamos en un DataFrame de Pandas
        clientes_df = pd.read_sql_query("SELECT id, nombre, email, telefono, objetivo FROM clientes", conn)
        conn.close()

        if not clientes_df.empty:
            # Mostramos la tabla de clientes usando Streamlit
            st.dataframe(clientes_df, use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay clientes registrados.")

    except Exception as e:
        st.error(f"No se pudo cargar la lista de clientes: {e}")
