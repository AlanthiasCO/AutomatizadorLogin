import sys
from dotenv import load_dotenv
import time
import json
import os
import socket
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from tkinter import Tk, Label, OptionMenu, StringVar, Button, Listbox, messagebox, Frame
from datetime import datetime, timedelta

# --- CONSTANTES (Nenhuma alteração aqui) ---
URL_LOGIN = 'https://accounts.google.com/o/oauth2/auth/oauthchooseaccount?client_id=717821919461-ri9sne01f21k4p0b1acbkr5j65j2ph3h.apps.googleusercontent.com&redirect_uri=https%3A%2F%2Fwww.matific.com%2Fsocial%2Fcomplete%2Fparana-municipal%2F&response_type=code&scope=openid%20email%20profile&service=lso&o2v=1&flowName=GeneralOAuthFlow'
CREDENTIALS_PATH = (
    os.environ.get('CREDENTIALS_PATH')
    or (os.path.join(os.path.dirname(sys.executable), 'credentials.json') if hasattr(sys, 'executable') else 'credentials.json')
)
SPREADSHEET_NAME = "contas_app"
LOG_WORKSHEET_NAME = "Logs"
MACHINES_WORKSHEET_NAME = "Maquinas"
SESSION_DURATION_MINUTES = 35
WARNING_SECONDS = 5
SCOPE = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

load_dotenv()

CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH") or "credentials.json"

# --- TODAS AS FUNÇÕES DE LÓGICA PERMANECEM IDÊNTICAS ---

def carregar_cronograma():
    try:
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        json_path = os.path.join(base_path, 'cronograma.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        messagebox.showerror("Erro Crítico", "O arquivo 'cronograma.json' não foi encontrado!")
        sys.exit(1)
    except json.JSONDecodeError:
        messagebox.showerror("Erro Crítico", "O arquivo 'cronograma.json' contém um erro de sintaxe.")
        sys.exit(1)

# --- VARIÁVEIS GLOBAIS ---
ALL_USERS = []
root = None
CRONOGRAMA = carregar_cronograma()

gspread_creds = None
gspread_client = None
gspread_spreadsheet = None

MAPA_DIAS = {
    0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira",
    3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"
}

def verificar_horario_atual():
    agora = datetime.now()
    hora_atual = agora.time()
    dia_semana_num = agora.weekday()
    dia_semana_atual = MAPA_DIAS.get(dia_semana_num)
    for agendamento in CRONOGRAMA:
        if agendamento["dia"] == dia_semana_atual:
            inicio = datetime.strptime(agendamento["inicio"], "%H:%M").time()
            fim = datetime.strptime(agendamento["fim"], "%H:%M").time()
            if inicio <= hora_atual <= fim:
                return agendamento 
    return None

def perform_login(email, password):
    options = Options()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    try:
        driver.get(URL_LOGIN)
        email_field = WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, 'identifierId')))
        email_field.send_keys(email)
        driver.find_element(By.ID, 'identifierNext').click()
        password_field = WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.XPATH, "//input[@type='password']")))
        password_field.send_keys(password)
        driver.find_element(By.ID, 'passwordNext').click()
        print(f"Login com a conta '{email}' realizado com sucesso.")
        return driver
    except Exception as e:
        messagebox.showerror("Erro de Login", f"Erro ao logar com {email}:\n{e}")
        driver.quit()
        return None

def processar_acesso_filtrado(spreadsheet, user_data, machine_name, timestamp_atual):
    try:
        try:
            worksheet = spreadsheet.worksheet("acessos_filtrados")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title="acessos_filtrados", rows="1000", cols="1")
            worksheet.append_row(["Registro de Acesso Significativo"])
        registros = worksheet.get_all_values()
        ultimo_registro_da_maquina = None
        for registro in reversed(registros):
            if machine_name in registro[0]:
                ultimo_registro_da_maquina = registro[0]
                break
        if ultimo_registro_da_maquina is None:
            novo_registro = f"{user_data['nome']} acessou na {machine_name} - {timestamp_atual.strftime('%d/%m/%Y %H:%M:%S')}"
            worksheet.append_row([novo_registro])
            return
        partes = ultimo_registro_da_maquina.split(' - ')
        timestamp_anterior_str = partes[-1]
        nome_anterior = partes[0].split(' acessou na ')[0]
        timestamp_anterior = datetime.strptime(timestamp_anterior_str, '%d/%m/%Y %H:%M:%S')
        if user_data['nome'] != nome_anterior:
            novo_registro = f"{user_data['nome']} acessou na {machine_name} - {timestamp_atual.strftime('%d/%m/%Y %H:%M:%S')}"
            worksheet.append_row([novo_registro])
            return
        diferenca_tempo = timestamp_atual - timestamp_anterior
        if diferenca_tempo > timedelta(hours=2):
            novo_registro = f"{user_data['nome']} acessou na {machine_name} - {timestamp_atual.strftime('%d/%m/%Y %H:%M:%S')}"
            worksheet.append_row([novo_registro])
    except Exception as e:
        print(f"ERRO AO PROCESSAR ACESSO FILTRADO: {e}")

def register_log(user_data):
    try:
        hostname = socket.gethostname()
        machine_name_to_log = hostname
        spreadsheet = gspread_spreadsheet
        try:
            worksheet_machines = spreadsheet.worksheet(MACHINES_WORKSHEET_NAME)
            machine_list = worksheet_machines.get_all_records()
            machine_map = {item["Hostname"]: item["Apelido"] for item in machine_list}
            machine_name_to_log = machine_map.get(hostname, hostname)
        except Exception as e:
            print(f"Erro ao ler a aba de máquinas: {e}. Usando hostname real.")
        agora = datetime.now()
        data_atual = agora.strftime("%d/%m/%Y")
        hora_atual = agora.strftime("%H:%M:%S")
        processar_acesso_filtrado(spreadsheet, user_data, machine_name_to_log, agora)
        log_row = [data_atual, hora_atual, user_data['nome'], user_data['email'], user_data['escola'], machine_name_to_log]
        worksheet_logs = spreadsheet.worksheet(LOG_WORKSHEET_NAME)
        worksheet_logs.append_row(log_row)
        print(f"Log registrado com sucesso para: {user_data['nome']} na máquina '{machine_name_to_log}'")
    except Exception as e:
        print(f"ERRO GERAL AO REGISTRAR O LOG: {e}")

def load_data():
    global ALL_USERS, gspread_creds, gspread_client, gspread_spreadsheet
    ALL_USERS = []
    try:
        if gspread_client is None:
            gspread_creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
            gspread_client = gspread.authorize(gspread_creds)
        if gspread_spreadsheet is None:
            gspread_spreadsheet = gspread_client.open(SPREADSHEET_NAME)
        sheet = gspread_spreadsheet.sheet1
        sheet_data = sheet.get_all_records()
        if not sheet_data:
            messagebox.showerror("Erro", "A planilha está vazia ou não pôde ser lida.")
            sys.exit(1)
        for row in sheet_data:
            new_row = {'nome': row['full_name'], 'email': row['email'], 'senha': row['senha'], 'escola': str(row['descescola']).strip()}
            column_name = str(row.get('name', '')).strip()
            if ' - ' in column_name:
                parts = column_name.split(' - ', 1)
                new_row['serie'] = parts[0].strip()
                new_row['periodo'] = parts[1].strip()
            else:
                new_row['serie'] = column_name; new_row['periodo'] = ''
            ALL_USERS.append(new_row)
    except FileNotFoundError:
        messagebox.showerror("Erro de Autenticação", f"Arquivo de credenciais '{CREDENTIALS_PATH}' não encontrado.")
        sys.exit(1)
    except gspread.exceptions.SpreadsheetNotFound:
        messagebox.showerror("Erro de Acesso", f"Planilha '{SPREADSHEET_NAME}' não encontrada.")
        sys.exit(1)
    except Exception as e:
        messagebox.showerror("Erro Inesperado", f"Ocorreu um erro ao carregar os dados:\n{e}")
        sys.exit(1)

def update_options(*args):
    school_selected = var_school.get()
    period_selected = var_period.get()
    series_selected = var_series.get()
    if (school_selected != "Selecione a Escola" and period_selected and series_selected != "Selecione a Série"):
        filtered_users = [user for user in ALL_USERS if user['escola'] == school_selected and user['periodo'] == period_selected and user['serie'] == series_selected]
        name_list.delete(0, 'end')
        for user in sorted(filtered_users, key=lambda u: u['nome']):
            name_list.insert('end', user['nome'])
    else:
        name_list.delete(0, 'end')

def start_login():
    try:
        selected_name = name_list.get(name_list.curselection())
        user = next(u for u in ALL_USERS if u['nome'] == selected_name)
        register_log(user)
        email = user['email']
        password = user['senha']
        root.destroy()
        driver = perform_login(email, password)
        if driver:
            manage_session(driver)
    except IndexError:
        messagebox.showwarning("Aviso", "Por favor, selecione um nome da lista.")
    except Exception as e:
        messagebox.showerror("Erro", f"Ocorreu um erro: {e}")
        start_application()

def manage_session(driver):
    start_time = time.time()
    timeout = SESSION_DURATION_MINUTES * 60
    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                messagebox.showinfo("Troca de Jogador", "Seu tempo acabou! Agora é a vez do seu colega jogar.")
                time.sleep(WARNING_SECONDS)
                break
            try:
                if not driver.window_handles: break
            except WebDriverException: break
            time.sleep(1)
    finally:
        try: driver.quit()
        except Exception: pass
    sys.exit(0)

# --- FUNÇÃO DA INTERFACE (ÚNICA PARTE ALTERADA) ---

def start_application():
    global root, var_school, var_period, var_series, name_list, gspread_client, gspread_spreadsheet
    load_data()

    if gspread_client is None:
        gspread_creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
        gspread_client = gspread.authorize(gspread_creds)
    if gspread_spreadsheet is None:
        gspread_spreadsheet = gspread_client.open(SPREADSHEET_NAME)

    try:
        gspread_spreadsheet.worksheet(LOG_WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = gspread_spreadsheet.add_worksheet(title=LOG_WORKSHEET_NAME, rows="1000", cols="10")
        ws.append_row(["Data", "Hora", "Nome Aluno", "Email", "Escola", "Nome da Máquina"])
    try:
        gspread_spreadsheet.worksheet(MACHINES_WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        gspread_spreadsheet.add_worksheet(title=MACHINES_WORKSHEET_NAME, rows="1000", cols="2")
    try:
        gspread_spreadsheet.worksheet("acessos_filtrados")
    except gspread.exceptions.WorksheetNotFound:
        ws = gspread_spreadsheet.add_worksheet(title="acessos_filtrados", rows="1000", cols="1")
        ws.append_row(["Registro de Acesso Significativo"])
    
    root = Tk()
    root.title("Automatizador de Login")
    
    window_width = 500
    window_height = 620
    
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    center_x = int(screen_width/2 - window_width / 2)
    center_y = int(screen_height/2 - window_height / 2)
    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
    
    # NOVA PALETA DE CORES - TEMA CLARO
    CORES = {
        "fundo": "#F0F0F0",
        "texto_principal": "#000000",
        "texto_secundario": "#555555",
        "fundo_widget": "#FFFFFF",
        "destaque": "#0078D7",
        "texto_destaque": "#FFFFFF"
    }
    
    root.configure(bg=CORES["fundo"])
    root.resizable(False, False)

    main_frame = Frame(root, bg=CORES["fundo"], padx=30, pady=20)
    main_frame.pack(expand=True, fill="both")

    label_font = ("Segoe UI", 11)
    option_font = ("Segoe UI", 10)
    
    turma_permitida = verificar_horario_atual()

    var_school = StringVar(root)
    var_period = StringVar(root)
    var_series = StringVar(root)

    # --- Configuração dos Widgets com o novo tema ---
    
    Label(main_frame, text="Escola:", bg=CORES["fundo"], fg=CORES["texto_principal"], font=label_font).pack(anchor="w", pady=(5, 2))
    school_menu = OptionMenu(main_frame, var_school, "")
    school_menu.config(font=option_font, bg=CORES["fundo_widget"], fg=CORES["texto_principal"], relief="solid", highlightthickness=1, borderwidth=1, activebackground=CORES["fundo_widget"])
    school_menu["menu"].config(font=option_font, bg=CORES["fundo_widget"], fg=CORES["texto_principal"])
    school_menu.pack(fill="x", ipady=5, pady=(0, 10))

    Label(main_frame, text="Período:", bg=CORES["fundo"], fg=CORES["texto_principal"], font=label_font).pack(anchor="w", pady=(5, 2))
    period_menu = OptionMenu(main_frame, var_period, "")
    period_menu.config(font=option_font, bg=CORES["fundo_widget"], fg=CORES["texto_principal"], relief="solid", highlightthickness=1, borderwidth=1, activebackground=CORES["fundo_widget"])
    period_menu["menu"].config(font=option_font, bg=CORES["fundo_widget"], fg=CORES["texto_principal"])
    period_menu.pack(fill="x", ipady=5, pady=(0, 10))

    Label(main_frame, text="Série:", bg=CORES["fundo"], fg=CORES["texto_principal"], font=label_font).pack(anchor="w", pady=(5, 2))
    series_menu = OptionMenu(main_frame, var_series, "")
    series_menu.config(font=option_font, bg=CORES["fundo_widget"], fg=CORES["texto_principal"], relief="solid", highlightthickness=1, borderwidth=1, activebackground=CORES["fundo_widget"])
    series_menu["menu"].config(font=option_font, bg=CORES["fundo_widget"], fg=CORES["texto_principal"])
    series_menu.pack(fill="x", ipady=5, pady=(0, 10))

    Label(main_frame, text="Selecione seu nome:", bg=CORES["fundo"], fg=CORES["texto_principal"], font=label_font).pack(anchor="w", pady=(15, 5))
    name_list = Listbox(main_frame, height=8, font=("Segoe UI", 11), bg=CORES["fundo_widget"], fg=CORES["texto_principal"],
                        selectbackground=CORES["destaque"], selectforeground=CORES["texto_destaque"], 
                        relief="solid", highlightthickness=0, borderwidth=1)
    name_list.pack(fill="both", expand=True, pady=(0, 15))

    login_btn = Button(main_frame, text="Fazer Login", command=start_login, font=("Segoe UI", 12, "bold"),
                       bg=CORES["destaque"], fg=CORES["texto_destaque"], relief="flat", pady=8)
    login_btn.pack(pady=10, fill='x')

    # Lógica de bloqueio de horário (sem alteração funcional)
    if turma_permitida:
        var_school.set(turma_permitida['escola'])
        var_period.set(turma_permitida['turma']) 
        var_series.set(turma_permitida['serie'])
        
        # Estilo para widgets desabilitados
        disabled_style = {"bg": "#E5E5E5", "fg": "#A0A0A0"}
        school_menu.config(state="disabled", **disabled_style)
        period_menu.config(state="disabled", **disabled_style)
        series_menu.config(state="disabled", **disabled_style)

        update_options()

        if name_list.size() == 0:
            full_turma_name = f"{turma_permitida['serie']} - {turma_permitida['turma']} - {turma_permitida['escola']}"
            Label(main_frame, text=f"Turma agendada ({full_turma_name}) não encontrada.",
                  bg=CORES["fundo"], fg="orange", font=label_font).pack(pady=5)
            login_btn.config(state="disabled")

    else:
        var_school.set("Fora do horário de aula")
        var_period.set("Nenhum login permitido")
        var_series.set("Tente novamente mais tarde")
        
        disabled_style = {"bg": "#E5E5E5", "fg": "#A0A0A0"}
        school_menu.config(state="disabled", **disabled_style)
        period_menu.config(state="disabled", **disabled_style)
        series_menu.config(state="disabled", **disabled_style)
        login_btn.config(state="disabled")

    footer_text = "Desenvolvido por Alan Mathias | Para mais informações: alanmathiasctt@gmail.com"
    footer_label = Label(main_frame, text=footer_text, font=("Segoe UI", 8), bg=CORES["fundo"], fg=CORES["texto_secundario"])
    footer_label.pack(side="bottom", pady=(10, 0))

    root.mainloop()

if __name__ == "__main__":
    start_application()