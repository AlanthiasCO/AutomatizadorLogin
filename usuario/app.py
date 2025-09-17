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


# --- CONSTANTES ---
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

def carregar_cronograma():
    # Carrega o cronograma a partir do arquivo json
    try:
        # Encontra o caminho correto, funcione tanto em modo normal quanto em .exe
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

# Variáveis globais para gspread
gspread_creds = None
gspread_client = None
gspread_spreadsheet = None

MAPA_DIAS = {
    0: "Segunda-feira", 1: "Terça-feira", 2: "Quarta-feira",
    3: "Quinta-feira", 4: "Sexta-feira", 5: "Sábado", 6: "Domingo"
}

def verificar_horario_atual():
    # Verifica o dia e hora atuais e retorna a turma permitida conforme o CRONOGRAMA.
    # Retorna um dicionário com 'escola' e 'serie' se houver uma turma, senão None.

    agora = datetime.now()
    hora_atual = agora.time()
    dia_semana_num = agora.weekday() # Segunda é 0, Terça é 1...

    dia_semana_atual = MAPA_DIAS.get(dia_semana_num)



    for agendamento in CRONOGRAMA:
        if agendamento["dia"] == dia_semana_atual:
            inicio = datetime.strptime(agendamento["inicio"], "%H:%M").time()
            fim = datetime.strptime(agendamento["fim"], "%H:%M").time()
            if inicio <= hora_atual <= fim:
                return agendamento 
    return None

def perform_login(email, password):
# Função para executar o processo de login e retornar a instância do driver.
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
            print(f"Primeiro acesso registrado para a máquina {machine_name}.")
            novo_registro = f"{user_data['nome']} acessou na {machine_name} - {timestamp_atual.strftime('%d/%m/%Y %H:%M:%S')}"
            worksheet.append_row([novo_registro])
            return

        partes = ultimo_registro_da_maquina.split(' - ')
        timestamp_anterior_str = partes[-1]
        nome_anterior = partes[0].split(' acessou na ')[0]
        
        timestamp_anterior = datetime.strptime(timestamp_anterior_str, '%d/%m/%Y %H:%M:%S')

        if user_data['nome'] != nome_anterior:
            print(f"Novo usuário ({user_data['nome']}) na máquina {machine_name}. Registrando acesso.")
            novo_registro = f"{user_data['nome']} acessou na {machine_name} - {timestamp_atual.strftime('%d/%m/%Y %H:%M:%S')}"
            worksheet.append_row([novo_registro])
            return
            
        diferenca_tempo = timestamp_atual - timestamp_anterior
        
        if diferenca_tempo > timedelta(hours=2):
            print(f"Mesmo usuário ({user_data['nome']}) após 2h. Registrando novo acesso.")
            novo_registro = f"{user_data['nome']} acessou na {machine_name} - {timestamp_atual.strftime('%d/%m/%Y %H:%M:%S')}"
            worksheet.append_row([novo_registro])
            return

        print(f"Acesso repetido de {user_data['nome']} em menos de 2h. Não registrando.")

    except Exception as e:
        print(f"ERRO AO PROCESSAR ACESSO FILTRADO: {e}")


def register_log(user_data):
# Registra o acesso de um usuário, traduzindo o nome da máquina usando a aba 'Maquinas'.
    try:
        print("Iniciando registro de log...")
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
        
        log_row = [
            data_atual, 
            hora_atual, 
            user_data['nome'], 
            user_data['email'], 
            user_data['escola'], 
            machine_name_to_log
        ]                    

        worksheet_logs = spreadsheet.worksheet(LOG_WORKSHEET_NAME)

        
        worksheet_logs.append_row(log_row)
        print(f"Log registrado com sucesso para: {user_data['nome']} na máquina '{machine_name_to_log}'")

    except Exception as e:
        print(f"ERRO GERAL AO REGISTRAR O LOG: {e}")

def load_data():
    global ALL_USERS
    ALL_USERS = []
    try:
        global gspread_creds, gspread_client, gspread_spreadsheet
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
            new_row = {
                'nome': row['full_name'], 'email': row['email'], 'senha': row['senha'],
                'escola': str(row['descescola']).strip(),
            }
            column_name = str(row.get('name', '')).strip()
            if ' - ' in column_name:
                parts = column_name.split(' - ', 1)
                new_row['serie'] = parts[0].strip()
                new_row['periodo'] = parts[1].strip()
            else:
                new_row['serie'] = column_name; new_row['periodo'] = ''
            ALL_USERS.append(new_row)

    except FileNotFoundError:
        messagebox.showerror( "Erro de Autenticação", f"Arquivo de credenciais '{CREDENTIALS_PATH}' não encontrado.")
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
    
    # Condição alterada para lidar com os valores pré-selecionados
    if (school_selected != "Selecione a Escola" and period_selected and series_selected != "Selecione a Série"):
        filtered_users = [
            user for user in ALL_USERS
            if user['escola'] == school_selected and user['periodo'] == period_selected and user['serie'] == series_selected
        ]
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
        print(f"Erro em start_login: {e}")
        messagebox.showerror("Erro", f"Ocorreu um erro: {e}")
        start_application()

def manage_session(driver):
# Gerencia a sessão, monitorando se o navegador foi fechado e encerrando o tempo.
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
                if not driver.window_handles:
                    print("Navegador fechado manualmente. Encerrando.")
                    break
            except WebDriverException:
                print("WebDriverException: navegador fechado. Encerrando.")
                break
            time.sleep(1)
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    sys.exit(0)

def start_application():
    global root, var_school, var_period, var_series, name_list, gspread_client, gspread_spreadsheet
    load_data()

    # Inicializa gspread client e spreadsheet se ainda não estiverem inicializados
    if gspread_client is None:
        gspread_creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
        gspread_client = gspread.authorize(gspread_creds)
    if gspread_spreadsheet is None:
        gspread_spreadsheet = gspread_client.open(SPREADSHEET_NAME)

    # Garante que as worksheets de log e máquinas existam
    try:
        gspread_spreadsheet.worksheet(LOG_WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = gspread_spreadsheet.add_worksheet(title=LOG_WORKSHEET_NAME, rows="1000", cols="10")
        ws.append_row(["Data", "Hora", "Nome Aluno", "Email", "Escola", "Nome da Máquina"])
    
    try:
        gspread_spreadsheet.worksheet(MACHINES_WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        # Cria a worksheet de máquinas se não existir, sem cabeçalho inicial
        gspread_spreadsheet.add_worksheet(title=MACHINES_WORKSHEET_NAME, rows="1000", cols="2")

    try:
        gspread_spreadsheet.worksheet("acessos_filtrados")
    except gspread.exceptions.WorksheetNotFound:
        ws = gspread_spreadsheet.add_worksheet(title="acessos_filtrados", rows="1000", cols="1")
        ws.append_row(["Registro de Acesso Significativo"])

    
    root = Tk()
    root.title("Automatizador de Login")
    
    window_width = 600
    window_height = 680
    
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    center_x = int(screen_width/2 - window_width / 2)
    center_y = int(screen_height/2 - window_height / 2)
    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
    
    root.configure(bg="#2B2B3A")
    root.resizable(False, False)

    main_frame = Frame(root, bg="#2B2B3A", padx=30, pady=20)
    main_frame.pack(expand=True, fill="both")

    label_font = ("Segoe UI", 12)
    option_font = ("Segoe UI", 11)
    
    text_color = "#E8E6E3"
    bg_color = "#2B2B3A"
    widget_bg = "#3A3A4A"
    button_bg = "#7B61FF"
    button_fg = "white"

    turma_permitida = verificar_horario_atual()

    # Criação das variáveis e menus
    var_school = StringVar(root)
    var_period = StringVar(root) #'period' está sendo usado para a 'turma' (A, B...)
    var_series = StringVar(root)

    Label(main_frame, text="Escola:", bg=bg_color, fg=text_color, font=label_font).pack(anchor="w", pady=(10, 5))
    school_menu = OptionMenu(main_frame, var_school, "")
    school_menu.config(font=option_font, bg=widget_bg, fg=text_color, relief="flat", highlightthickness=0, activebackground=widget_bg, activeforeground=text_color)
    school_menu["menu"].config(font=option_font, bg=widget_bg, fg=text_color)
    school_menu.pack(fill="x", ipady=5, pady=(0, 10))

    Label(main_frame, text="Período:", bg=bg_color, fg=text_color, font=label_font).pack(anchor="w", pady=(10, 5))
    period_menu = OptionMenu(main_frame, var_period, "")
    period_menu.config(font=option_font, bg=widget_bg, fg=text_color, relief="flat", highlightthickness=0, activebackground=widget_bg, activeforeground=text_color)
    period_menu["menu"].config(font=option_font, bg=widget_bg, fg=text_color)
    period_menu.pack(fill="x", ipady=5, pady=(0, 10))

    Label(main_frame, text="Série:", bg=bg_color, fg=text_color, font=label_font).pack(anchor="w", pady=(10, 5))
    series_menu = OptionMenu(main_frame, var_series, "")
    series_menu.config(font=option_font, bg=widget_bg, fg=text_color, relief="flat", highlightthickness=0, activebackground=widget_bg, activeforeground=text_color)
    series_menu["menu"].config(font=option_font, bg=widget_bg, fg=text_color)
    series_menu.pack(fill="x", ipady=5, pady=(0, 10))

    Label(main_frame, text="Selecione seu nome:", bg=bg_color, fg=text_color, font=label_font).pack(anchor="w", pady=(15, 5))
    name_list = Listbox(main_frame, height=8, font=("Segoe UI", 11), bg=widget_bg, fg=text_color,
                        selectbackground=button_bg, selectforeground="white", relief="flat", highlightthickness=0)
    name_list.pack(fill="both", expand=True, pady=(0, 15))

    login_btn = Button(main_frame, text="Fazer Login", command=start_login, font=("Segoe UI", 12, "bold"),
                       bg=button_bg, fg=button_fg, relief="flat", pady=10)
    login_btn.pack(pady=10, fill='x')

    # Se estiver dentro de um horário de aula permitido
    if turma_permitida:
        escola_permitida = turma_permitida['escola']
        serie_permitida = turma_permitida['serie']
        turma_agendada = turma_permitida['turma'] 

        # Preenche e desabilita os menus diretamente com os dados do cronograma
        var_school.set(escola_permitida)
        var_period.set(turma_agendada) 
        var_series.set(serie_permitida)
        
        school_menu.config(state="disabled")
        period_menu.config(state="disabled")
        series_menu.config(state="disabled")

        update_options()

        # Verifica se a lista de nomes está vazia após a atualização
        if name_list.size() == 0:
            full_turma_name = f"{serie_permitida} - {turma_agendada} - {escola_permitida}"
            Label(main_frame, text=f"Turma agendada ({full_turma_name}) não encontrada na planilha.",
                  bg=bg_color, fg="orange", font=label_font).pack(pady=5)
            login_btn.config(state="disabled")

    else:
        var_school.set("Fora do horário de aula")
        var_period.set("Nenhum login permitido")
        var_series.set("Tente novamente mais tarde")

        school_menu.config(state="disabled")
        period_menu.config(state="disabled")
        series_menu.config(state="disabled")
        login_btn.config(state="disabled")

    footer_text = "Desenvolvido por Alan Mathias | Para mais informações: alanmathiasctt@gmail.com"
    footer_label = Label(main_frame, text=footer_text, font=("Segoe UI", 8), bg=bg_color, fg="#A0A0A0")
    footer_label.pack(side="bottom", pady=(10, 0))

    root.mainloop()

if __name__ == "__main__":
    start_application()