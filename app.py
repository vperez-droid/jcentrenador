import streamlit as st
from PIL import Image
import sqlite3
import pandas as pd
import os
from passlib.context import CryptContext
import datetime

# --- CONFIGURACIÓN DE LA PÁGINA Y SEGURIDAD ---
st.set_page_config(
    page_title="JCT - Panel de Entrenador",
    layout="wide"
)

# Inicializa el contexto de encriptación de contraseñas
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# --- GESTIÓN DE LA BASE DE DATOS ---
DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "jct_users.db")

def init_db():
    """Inicializa la DB, la tabla de usuarios y añade datos de ejemplo si está vacía."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Añadimos una columna para la fecha de registro para poder calcular métricas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            objetivo TEXT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            fecha_registro TEXT NOT NULL
        );
    ''')
    
    # Comprobar si la tabla está vacía antes de insertar datos ficticios
    cursor.execute("SELECT COUNT(*) FROM users")
    is_empty = cursor.fetchone()[0] == 0
    
    if is_empty:
        # Insertar datos de ejemplo solo la primera vez
        sample_users = [
            ("Ana García", "Pérdida de peso", "anagarcia", pwd_context.hash("ana2025"), "2025-09-15"),
            ("Carlos Sánchez", "Ganancia muscular", "csanchez", pwd_context.hash("carlosfit"), "2025-10-05"),
            ("Laura Martínez", "Rendimiento deportivo", "lauram", pwd_context.hash("runner25"), "2025-10-22")
        ]
        cursor.executemany("INSERT INTO users (nombre, objetivo, username, password_hash, fecha_registro) VALUES (?, ?, ?, ?, ?)", sample_users)

    conn.commit()
    conn.close()

def get_db_connection():
    """Establece conexión con la base de datos."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# --- GESTIÓN DE NAVEGACIÓN (ESTADO DE LA PÁGINA) ---
if 'page' not in st.session_state:
    st.session_state.page = 'inicio'

def set_page(page):
    """Función para cambiar de página."""
    st.session_state.page = page

# --- PÁGINA DE INICIO (LANDING PAGE) ---
if st.session_state.page == 'inicio':
    col1, col2, col3 = st.columns([2, 3, 2])
    with col2:
        st.title("Panel de Entrenador - JCT")
        try:
            image = Image.open('assets/jct.jpeg')
            st.image(image, width=250)
        except FileNotFoundError:
            st.error("No se encontró el logo 'assets/jct.jpeg'.")

    st.write("---")
    st.header("Selecciona una opción")

    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        if st.button("👤 Registrar Cliente Nuevo", use_container_width=True, on_click=set_page, args=['registrar']):
            pass
    with col2:
        if st.button("📋 Clientes ya Registrados", use_container_width=True, on_click=set_page, args=['ver_clientes']):
            pass
    with col3:
        if st.button("📊 Centro de Control", use_container_width=True, on_click=set_page, args=['centro_control']):
            pass

# --- PÁGINA PARA REGISTRAR CLIENTE ---
elif st.session_state.page == 'registrar':
    if st.button("⬅️ Volver al inicio"):
        set_page('inicio')
        st.rerun()
        
    st.title("👤 Formulario de Creación de Cliente")
    with st.form("crear_cliente_form", clear_on_submit=True):
        nombre = st.text_input("Nombre completo del cliente *")
        objetivo = st.selectbox("Selecciona el objetivo principal", ["Recomposición corporal", "Fuerza", "Pérdida de peso", "Ganancia muscular", "Otro"])
        username = st.text_input("Nombre de Usuario para el cliente *")
        password = st.text_input("Contraseña para el cliente *", type="password")
        
        if st.form_submit_button("✅ Crear Cliente"):
            if not all([nombre, username, password]):
                st.warning("Todos los campos marcados con * son obligatorios.")
            else:
                try:
                    hashed_password = pwd_context.hash(password)
                    registration_date = datetime.date.today().isoformat()
                    conn = get_db_connection()
                    conn.execute(
                        "INSERT INTO users (nombre, objetivo, username, password_hash, fecha_registro) VALUES (?, ?, ?, ?, ?)",
                        (nombre, objetivo, username, hashed_password, registration_date)
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"¡Cliente '{nombre}' creado con éxito!")
                except sqlite3.IntegrityError:
                    st.error(f"El nombre de usuario '{username}' ya existe.")
                except Exception as e:
                    st.error(f"Error: {e}")

# --- PÁGINA PARA VER CLIENTES ---
elif st.session_state.page == 'ver_clientes':
    if st.button("⬅️ Volver al inicio"):
        set_page('inicio')
        st.rerun()
        
    st.title("📋 Lista de Clientes Registrados")
    try:
        conn = get_db_connection()
        clientes_df = pd.read_sql_query("SELECT id, nombre, username, objetivo, fecha_registro FROM users", conn)
        conn.close()
        if not clientes_df.empty:
            st.dataframe(clientes_df, use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay clientes registrados.")
    except Exception as e:
        st.error(f"No se pudo cargar la lista de clientes: {e}")

# --- PÁGINA DEL CENTRO DE CONTROL ---
elif st.session_state.page == 'centro_control':
    if st.button("⬅️ Volver al inicio"):
        set_page('inicio')
        st.rerun()

    st.title("📊 Centro de Control")
    conn = get_db_connection()
    
    # Métricas
    df = pd.read_sql_query("SELECT fecha_registro FROM users", conn)
    conn.close()
    
    total_clientes = len(df)
    mes_top = "N/A"
    
    if not df.empty:
        df['fecha_registro'] = pd.to_datetime(df['fecha_registro'])
        mes_con_mas_altas = df['fecha_registro'].dt.to_period('M').value_counts().idxmax()
        mes_top = mes_con_mas_altas.strftime('%B %Y').capitalize()

    col1, col2, col3 = st.columns(3)
    col1.metric("Clientes Actuales", f"{total_clientes}")
    col2.metric("Total Histórico", f"{total_clientes}")
    col3.metric("Mes con más altas", mes_top)
    
    st.write("---")
    st.subheader("Más datos y gráficos próximamente...")

# Inicializa la base de datos al principio de la ejecución si es necesario
if 'db_initialized' not in st.session_state:
    init_db()
    st.session_state.db_initialized = True
