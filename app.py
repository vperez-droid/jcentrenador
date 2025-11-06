import streamlit as st
from PIL import Image
import sqlite3
import pandas as pd
import os
from passlib.context import CryptContext
import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="JCT - Panel de Entrenador",
    page_icon="💪",
    layout="wide"
)

# --- INICIALIZACIÓN DE SEGURIDAD ---
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# --- GESTIÓN DE LA BASE DE DATOS ---
DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "jct_main.db")

def init_db():
    """Inicializa la DB y crea las tablas de usuarios y entrenamientos."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabla de Usuarios
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
    
    # --- NUEVA TABLA PARA ENTRENAMIENTOS ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entrenamientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            fecha_creacion TEXT NOT NULL,
            dia_semana TEXT,
            objetivo_sesion TEXT,
            warmup_general TEXT,
            specific_warmup TEXT,
            fuerza TEXT,
            trabajo_especifico TEXT,
            conditioning TEXT,
            anotaciones_coach TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    ''')

    # Añadir datos de ejemplo si la tabla de usuarios está vacía
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
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

# --- GESTIÓN DE NAVEGACIÓN Y ESTADO ---
if 'page' not in st.session_state:
    st.session_state.page = 'inicio'

def set_page(page):
    """Función para cambiar de página."""
    st.session_state.page = page

# --- PÁGINA DE INICIO (MENÚ PRINCIPAL) ---
def page_inicio():
    col1, col2, col3 = st.columns([2, 3, 2])
    with col2:
        st.title("Panel de Entrenador - JCT")
        try:
            image = Image.open('assets/jct.jpeg')
            st.image(image, use_column_width=True)
        except FileNotFoundError:
            st.warning("Logo no encontrado en 'assets/jct.jpeg'.")

    st.write("---")
    st.header("Selecciona una opción")

    c1, c2, c3, c4 = st.columns(4, gap="large")
    c1.button("👤 Registrar Cliente", use_container_width=True, on_click=set_page, args=['registrar'])
    c2.button("📋 Ver Clientes", use_container_width=True, on_click=set_page, args=['ver_clientes'])
    # --- NUEVO BOTÓN PARA CREAR ENTRENAMIENTO ---
    c3.button("💪 Crear Entrenamiento", use_container_width=True, on_click=set_page, args=['crear_entrenamiento'])
    c4.button("📊 Centro de Control", use_container_width=True, on_click=set_page, args=['centro_control'])

# --- PÁGINA PARA REGISTRAR CLIENTE ---
def page_registrar():
    if st.button("⬅️ Volver al inicio"):
        set_page('inicio')
        st.rerun()
        
    st.title("👤 Formulario de Creación de Cliente")
    with st.form("crear_cliente_form", clear_on_submit=True):
        nombre = st.text_input("Nombre completo *")
        objetivo = st.selectbox("Objetivo principal", ["Recomposición corporal", "Fuerza", "Pérdida de peso", "Ganancia muscular", "Otro"])
        username = st.text_input("Nombre de Usuario *")
        password = st.text_input("Contraseña *", type="password")
        
        if st.form_submit_button("✅ Crear Cliente"):
            if not all([nombre, username, password]):
                st.warning("Los campos con * son obligatorios.")
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
                    st.error(f"El usuario '{username}' ya existe.")
                except Exception as e:
                    st.error(f"Error: {e}")

# --- PÁGINA PARA VER CLIENTES ---
def page_ver_clientes():
    if st.button("⬅️ Volver al inicio"):
        set_page('inicio')
        st.rerun()
        
    st.title("📋 Lista de Clientes Registrados")
    try:
        conn = get_db_connection()
        clientes_df = pd.read_sql_query("SELECT id, nombre, username, objetivo, fecha_registro FROM users", conn)
        
        if not clientes_df.empty:
            st.dataframe(clientes_df, use_container_width=True, hide_index=True)
            
            # --- NUEVO: Ver entrenamientos de un cliente ---
            st.subheader("Ver Entrenamientos por Cliente")
            cliente_seleccionado = st.selectbox("Elige un cliente para ver sus entrenamientos", options=clientes_df['nombre'], index=None, placeholder="Selecciona...")
            
            if cliente_seleccionado:
                user_id = clientes_df[clientes_df['nombre'] == cliente_seleccionado]['id'].iloc[0]
                entrenamientos_df = pd.read_sql_query(f"SELECT fecha_creacion, dia_semana, objetivo_sesion FROM entrenamientos WHERE user_id = {user_id} ORDER BY fecha_creacion DESC", conn)
                
                if not entrenamientos_df.empty:
                    st.write(f"**Historial de {cliente_seleccionado}:**")
                    st.dataframe(entrenamientos_df, use_container_width=True, hide_index=True)
                else:
                    st.info(f"{cliente_seleccionado} aún no tiene entrenamientos registrados.")
        else:
            st.info("Aún no hay clientes registrados.")
        conn.close()
    except Exception as e:
        st.error(f"No se pudo cargar la lista de clientes: {e}")

# --- PÁGINA PARA CREAR ENTRENAMIENTO (NUEVA) ---
def page_crear_entrenamiento():
    if st.button("⬅️ Volver al inicio"):
        # Limpiar estado del asistente al volver
        for key in st.session_state.keys():
            if key.startswith('wizard_'):
                del st.session_state[key]
        set_page('inicio')
        st.rerun()

    st.title("💪 Creador de Sesiones de Entrenamiento")

    # Inicializar el estado del asistente
    if 'wizard_step' not in st.session_state:
        st.session_state.wizard_step = 1
        st.session_state.wizard_data = {}

    # --- PASO 1: SELECCIONAR CLIENTE Y FECHA ---
    if st.session_state.wizard_step == 1:
        st.subheader("Paso 1: Datos Generales")
        conn = get_db_connection()
        clientes = pd.read_sql_query("SELECT id, nombre FROM users", conn)
        conn.close()

        if clientes.empty:
            st.warning("No hay clientes registrados. Por favor, registra un cliente primero.")
            return

        cliente_id = st.selectbox("Selecciona el cliente", options=clientes['id'], format_func=lambda x: clientes[clientes['id'] == x]['nombre'].iloc[0])
        st.session_state.wizard_data['user_id'] = cliente_id

        col1, col2 = st.columns(2)
        with col1:
            st.session_state.wizard_data['fecha_creacion'] = st.date_input("Fecha de la sesión")
        with col2:
            st.session_state.wizard_data['dia_semana'] = st.text_input("Día de la semana (Ej: LUNES 6)")

        if st.button("Siguiente ➡️"):
            st.session_state.wizard_step = 2
            st.rerun()

    # --- PASO 2: DEFINIR SECCIONES DEL ENTRENAMIENTO ---
    elif st.session_state.wizard_step == 2:
        st.subheader("Paso 2: Contenido de la Sesión")
        
        with st.container(border=True):
            st.session_state.wizard_data['objetivo_sesion'] = st.text_area("🎯 Objetivo de la Sesión", height=100)
        
        with st.container(border=True):
             # Usamos \n para separar los items en la base de datos
            st.session_state.wizard_data['warmup_general'] = st.text_area("Warm-Up General (un item por línea)", height=150)
        
        with st.container(border=True):
            st.session_state.wizard_data['specific_warmup'] = st.text_area("Specific Warm-Up", height=100)

        with st.container(border=True):
            st.session_state.wizard_data['fuerza'] = st.text_area("🏋️ Weightlifting / Strength (un item por línea)", height=150)
            
        with st.container(border=True):
            st.session_state.wizard_data['trabajo_especifico'] = st.text_area("⚡ Trabajo Específico (EMOM, etc.)", height=150)
            
        with st.container(border=True):
            st.session_state.wizard_data['conditioning'] = st.text_area("🏃 Conditioning (un item por línea)", height=150)
            
        with st.container(border=True):
            st.session_state.wizard_data['anotaciones_coach'] = st.text_area("📝 Anotaciones del Coach", height=100)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Anterior"):
                st.session_state.wizard_step = 1
                st.rerun()
        with col2:
            if st.button("💾 Guardar Entrenamiento"):
                try:
                    conn = get_db_connection()
                    data = st.session_state.wizard_data
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO entrenamientos (user_id, fecha_creacion, dia_semana, objetivo_sesion, warmup_general, specific_warmup, fuerza, trabajo_especifico, conditioning, anotaciones_coach)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            data.get('user_id'),
                            data.get('fecha_creacion').isoformat(),
                            data.get('dia_semana'),
                            data.get('objetivo_sesion'),
                            data.get('warmup_general'),
                            data.get('specific_warmup'),
                            data.get('fuerza'),
                            data.get('trabajo_especifico'),
                            data.get('conditioning'),
                            data.get('anotaciones_coach')
                        )
                    )
                    conn.commit()
                    conn.close()
                    st.success("¡Entrenamiento guardado con éxito!")
                    
                    # Limpiar estado y volver al inicio
                    for key in st.session_state.keys():
                        if key.startswith('wizard_'):
                            del st.session_state[key]
                    set_page('inicio')
                    st.rerun()

                except Exception as e:
                    st.error(f"Error al guardar el entrenamiento: {e}")


# --- PÁGINA DEL CENTRO DE CONTROL ---
def page_centro_control():
    if st.button("⬅️ Volver al inicio"):
        set_page('inicio')
        st.rerun()

    st.title("📊 Centro de Control")
    conn = get_db_connection()
    df_users = pd.read_sql_query("SELECT fecha_registro FROM users", conn)
    conn.close()

    total_clientes = len(df_users)
    mes_top = "N/A"
    
    if not df_users.empty:
        df_users['fecha_registro'] = pd.to_datetime(df_users['fecha_registro'])
        mes_con_mas_altas = df_users['fecha_registro'].dt.to_period('M').value_counts().idxmax()
        mes_top = mes_con_mas_altas.strftime('%B %Y').capitalize()

    col1, col2, col3 = st.columns(3)
    col1.metric("Clientes Actuales", f"{total_clientes}")
    col2.metric("Total Histórico", f"{total_clientes}")
    col3.metric("Mes con más altas", mes_top)
    
    st.write("---")
    st.subheader("Más datos y gráficos próximamente...")

# --- ROUTER PRINCIPAL DE LA APLICACIÓN ---
def main():
    # Inicializa la base de datos una sola vez
    if 'db_initialized' not in st.session_state:
        init_db()
        st.session_state.db_initialized = True

    # Selector de página
    if st.session_state.page == 'inicio':
        page_inicio()
    elif st.session_state.page == 'registrar':
        page_registrar()
    elif st.session_state.page == 'ver_clientes':
        page_ver_clientes()
    elif st.session_state.page == 'crear_entrenamiento':
        page_crear_entrenamiento()
    elif st.session_state.page == 'centro_control':
        page_centro_control()

if __name__ == "__main__":
    main()
