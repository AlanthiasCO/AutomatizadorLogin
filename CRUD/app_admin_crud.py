import sys
import os
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from tkinter import Tk, Label, Button, Listbox, messagebox, Frame, Entry, END, Scrollbar
from tkinter import filedialog

# --- CONSTANTES ---
CREDENTIALS_PATH = (
    os.environ.get('CREDENTIALS_PATH')
    or (os.path.join(os.path.dirname(sys.executable), 'credentials.json') if hasattr(sys, 'executable') else 'credentials.json')
)
SPREADSHEET_NAME = "contas_app"
ESCOPO = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
ESCOLAS = ['MONTEIRO LOBATO', 'JOHN KENNEDY', 'OLAVO BILAC', 'CESAR LATTES']
CABECALHO_ESPERADO = ['full_name', 'email', 'senha', 'name', 'descescola']

CORES = {
    "fundo_principal": "#F0F0F0", "fundo_sidebar": "#E0E0E0", "fundo_form": "#FFFFFF",
    "texto_principal": "#000000", "texto_label": "#333333", "fundo_widget": "#F5F5F5",
    "destaque_escola": "#0078D7", "texto_destaque": "#FFFFFF", "destaque_turma": "#005a9e",
    "botao_sucesso": "#28A745", "botao_alerta": "#FFC107", "texto_alerta": "#000000",
    "botao_perigo": "#DC3545", "botao_limpar": "#6c757d"
}

# --- VARIÁVEIS GLOBAIS DE ESTADO ---
gspread_client = None
sheet = None
TODOS_OS_ALUNOS = []
ALUNOS_EXIBIDOS = []

escola_selecionada = None 
turma_selecionada = None  
escola_expandida = None   

def conectar_planilha():
    global gspread_client, sheet
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, ESCOPO)
        gspread_client = gspread.authorize(creds)
        spreadsheet = gspread_client.open(SPREADSHEET_NAME)
        sheet = spreadsheet.sheet1
        return True
    except FileNotFoundError:
        messagebox.showerror("Erro Crítico", f"Arquivo de credenciais '{CREDENTIALS_PATH}' não encontrado.")
        return False
    except gspread.exceptions.SpreadsheetNotFound:
        messagebox.showerror("Erro Crítico", f"Planilha '{SPREADSHEET_NAME}' não encontrada.")
        return False
    except Exception as e:
        messagebox.showerror("Erro de Conexão", f"Não foi possível conectar à planilha:\n{e}")
        return False

def carregar_dados_da_planilha():
    global TODOS_OS_ALUNOS
    if not sheet: return
    try:
        TODOS_OS_ALUNOS = sheet.get_all_records()
    except Exception as e:
        messagebox.showerror("Erro ao Ler Dados", f"Não foi possível carregar os dados da planilha:\n{e}")
        TODOS_OS_ALUNOS = []

# --- FUNÇÕES DE LÓGICA (CRUD E IMPORTAÇÃO) ---

def adicionar_aluno(entries, root, atualizar_lista_func, redesenhar_sidebar_func):
    try:
        novo_aluno = {
            "full_name": entries['full_name'].get().strip(), "email": entries['email'].get().strip(),
            "senha": entries['senha'].get().strip(), "descescola": entries['descescola'].get().strip(),
            "name": f"{entries['serie'].get().strip()} - {entries['turma'].get().strip()}"
        }
        if not all([novo_aluno["full_name"], novo_aluno["email"], novo_aluno["descescola"]]):
            messagebox.showwarning("Campos Vazios", "Nome, Email e Escola são obrigatórios.", parent=root)
            return
        
        header = sheet.row_values(1)
        row_to_append = [novo_aluno.get(h, "") for h in header]
        sheet.append_row(row_to_append)
        
        messagebox.showinfo("Sucesso", "Aluno adicionado com sucesso!", parent=root)
        carregar_dados_da_planilha()
        redesenhar_sidebar_func()
        atualizar_lista_func()
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao adicionar aluno: {e}", parent=root)

def editar_aluno(entries, user_listbox, root, atualizar_lista_func, redesenhar_sidebar_func):
    try:
        selected_index = user_listbox.curselection()[0]
        aluno_original = ALUNOS_EXIBIDOS[selected_index]
        email_original = aluno_original.get('email')

        dados_atualizados = {
            "full_name": entries['full_name'].get().strip(), "email": entries['email'].get().strip(),
            "senha": entries['senha'].get().strip(), "descescola": entries['descescola'].get().strip(),
            "name": f"{entries['serie'].get().strip()} - {entries['turma'].get().strip()}"
        }
        
        cell = sheet.find(email_original)
        if not cell:
            messagebox.showerror("Erro", "Aluno não encontrado na planilha para atualização.", parent=root)
            return

        header = sheet.row_values(1)
        row_to_update = [dados_atualizados.get(h, "") for h in header]
        sheet.update(f'A{cell.row}:{chr(ord("A")+len(header)-1)}{cell.row}', [row_to_update])
        
        messagebox.showinfo("Sucesso", "Dados do aluno atualizados!", parent=root)
        carregar_dados_da_planilha()
        redesenhar_sidebar_func()
        atualizar_lista_func()
    except IndexError:
        messagebox.showwarning("Aviso", "Selecione um aluno para editar.", parent=root)
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao editar aluno: {e}", parent=root)

def remover_aluno(user_listbox, root, atualizar_lista_func, redesenhar_sidebar_func):
    try:
        selected_index = user_listbox.curselection()[0]
        aluno_para_remover = ALUNOS_EXIBIDOS[selected_index]
        if not messagebox.askyesno("Confirmar Remoção", f"Tem certeza que deseja remover {aluno_para_remover.get('full_name')}?", parent=root):
            return

        cell = sheet.find(aluno_para_remover.get('email'))
        if not cell:
            messagebox.showerror("Erro", "Aluno não encontrado na planilha para remoção.", parent=root)
            return
        
        sheet.delete_rows(cell.row)
        messagebox.showinfo("Sucesso", "Aluno removido com sucesso!", parent=root)
        carregar_dados_da_planilha()
        redesenhar_sidebar_func()
        atualizar_lista_func()
    except IndexError:
        messagebox.showwarning("Aviso", "Selecione um aluno para remover.", parent=root)
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao remover aluno: {e}", parent=root)

def importar_banco_de_dados(root, atualizar_lista_func, redesenhar_sidebar_func):
    filepath = filedialog.askopenfilename(
        title="Selecione o arquivo de banco de dados",
        filetypes=(("Arquivos CSV", "*.csv"), ("Todos os arquivos", "*.*"))
    )
    if not filepath: return

    try:
        try:
            df = pd.read_csv(filepath)
        except Exception:
            df = pd.read_csv(filepath, delimiter=';')

        if list(df.columns) != CABECALHO_ESPERADO:
            messagebox.showerror("Erro de Cabeçalho", f"O arquivo importado não possui o cabeçalho esperado.\n\nEsperado: {CABECALHO_ESPERADO}\nEncontrado: {list(df.columns)}", parent=root)
            return
        
        if not messagebox.askyesno("CONFIRMAÇÃO CRÍTICA", "Esta ação irá APAGAR TODOS os dados atuais e substituí-los pelos dados do arquivo.\n\nEsta operação não pode ser desfeita.\n\nDeseja continuar?", parent=root):
            return

        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.values.tolist())
        
        messagebox.showinfo("Sucesso", "Banco de dados importado e substituído com sucesso!", parent=root)
        carregar_dados_da_planilha()
        redesenhar_sidebar_func()
        atualizar_lista_func()
    except Exception as e:
        messagebox.showerror("Erro na Importação", f"Ocorreu um erro ao processar o arquivo:\n{e}", parent=root)

def criar_interface_crud():
    root = Tk()
    root.title("Ferramenta Administrativa - Gestão de Alunos")
    root.geometry("1100x700")
    root.configure(bg=CORES["fundo_principal"])
    root.minsize(1000, 600)

    # --- Frames Principais ---
    frame_sidebar = Frame(root, bg=CORES["fundo_sidebar"], width=250, padx=10, pady=20)
    frame_sidebar.pack(side="left", fill="y")
    frame_sidebar.pack_propagate(False)
    
    frame_conteudo = Frame(root, bg=CORES["fundo_principal"], padx=20, pady=20)
    frame_conteudo.pack(side="right", fill="both", expand=True)
    frame_lista = Frame(frame_conteudo, bg=CORES["fundo_principal"])
    frame_lista.pack(side="left", fill="both", expand=True, padx=(0, 10))
    frame_form = Frame(frame_conteudo, bg=CORES["fundo_form"], padx=20, pady=20, relief="solid", bd=1)
    frame_form.pack(side="right", fill="y")

    # --- Widgets da Lista de Alunos ---
    Label(frame_lista, text="ALUNOS", font=("Segoe UI", 16, "bold"), bg=CORES["fundo_principal"], fg=CORES["texto_principal"]).pack(anchor="w")
    scrollbar = Scrollbar(frame_lista, orient="vertical")
    user_listbox = Listbox(frame_lista, font=("Segoe UI", 11), bg=CORES["fundo_widget"], fg=CORES["texto_principal"],
                           selectbackground=CORES["destaque_escola"], selectforeground=CORES["texto_destaque"],
                           relief="solid", borderwidth=1, highlightthickness=0, yscrollcommand=scrollbar.set)
    scrollbar.config(command=user_listbox.yview)
    scrollbar.pack(side="right", fill="y")
    user_listbox.pack(fill="both", expand=True, pady=(5,0))
    
    btn_importar = Button(frame_lista, text="Importar Novo Banco de Dados",
                          font=("Segoe UI", 10, "bold"), bg=CORES["destaque_escola"], fg=CORES["texto_destaque"],
                          relief="flat", pady=8, command=lambda: importar_banco_de_dados(root, atualizar_lista_alunos, redesenhar_sidebar))

    Label(frame_form, text="DADOS DO ALUNO", font=("Segoe UI", 14, "bold"), bg=CORES["fundo_form"], fg=CORES["texto_principal"]).grid(row=0, column=0, columnspan=2, pady=10, sticky="w")
    labels_map = {'full_name': "Nome Completo:", 'email': "Email:", 'senha': "Senha:", 'descescola': "Escola:", 'serie': "Série:", 'turma': "Turma"}
    entries = {}
    for i, (key, text) in enumerate(labels_map.items()):
        Label(frame_form, text=text, font=("Segoe UI", 11), bg=CORES["fundo_form"], fg=CORES["texto_label"]).grid(row=i+1, column=0, sticky="w", pady=6)
        entry = Entry(frame_form, font=("Segoe UI", 11), width=35, bg=CORES["fundo_widget"], fg=CORES["texto_principal"], relief="solid", borderwidth=1, insertbackground=CORES["texto_principal"])
        entry.grid(row=i+1, column=1, pady=6, padx=10)
        entries[key] = entry
    
    def on_user_select(event):
        try:
            selected_index = user_listbox.curselection()[0]
            aluno = ALUNOS_EXIBIDOS[selected_index]
            for entry in entries.values(): entry.delete(0, END)
            
            entries['full_name'].insert(0, aluno.get('full_name', ''))
            entries['email'].insert(0, aluno.get('email', ''))
            entries['senha'].insert(0, aluno.get('senha', ''))
            entries['descescola'].insert(0, aluno.get('descescola', ''))
            
            name_field = aluno.get('name', ' - ').split(' - ')
            entries['serie'].insert(0, name_field[0].strip())
            entries['turma'].insert(0, name_field[1].strip() if len(name_field) > 1 else '')
        except IndexError: pass
    user_listbox.bind('<<ListboxSelect>>', on_user_select)

    def limpar_campos():
        for entry in entries.values(): entry.delete(0, END)
        user_listbox.selection_clear(0, END)

    def atualizar_lista_alunos():
        global ALUNOS_EXIBIDOS
        
        alunos_filtrados = TODOS_OS_ALUNOS
        if escola_selecionada:
            alunos_filtrados = [u for u in alunos_filtrados if u.get('descescola') == escola_selecionada]
        if turma_selecionada:
            alunos_filtrados = [u for u in alunos_filtrados if u.get('name') == turma_selecionada]
            
        ALUNOS_EXIBIDOS = sorted(alunos_filtrados, key=lambda u: u.get('full_name', ''))
        
        user_listbox.delete(0, END)
        for aluno in ALUNOS_EXIBIDOS: user_listbox.insert(END, f"{aluno.get('full_name', 'N/A')}")
        limpar_campos()

    def redesenhar_sidebar():
        for widget in frame_sidebar.winfo_children(): widget.destroy()

        Label(frame_sidebar, text="CRUD - MATIFIC", font=("Segoe UI", 16, "bold"), bg=CORES["fundo_sidebar"], fg=CORES["texto_principal"]).pack(pady=(0, 10), anchor="w")

        btn_db_style = {"font": ("Segoe UI", 11, "bold"), "width": 22, "pady": 10, "relief": "flat", "bg": CORES["fundo_sidebar"], "fg": CORES["texto_principal"], "anchor": "w"}
        btn_db = Button(frame_sidebar, text="📁 BANCO DE DADOS", **btn_db_style, command=lambda: handle_clique_escola(None))
        btn_db.pack(pady=2, fill="x")
        if escola_selecionada is None:
            btn_db.config(bg=CORES["destaque_escola"], fg=CORES["texto_destaque"])
            btn_importar.pack(fill="x", pady=(10, 0))
        else:
            btn_importar.pack_forget()

        for escola in ESCOLAS:
            btn_escola_style = {"font": ("Segoe UI", 11), "width": 22, "pady": 10, "relief": "flat", "bg": CORES["fundo_sidebar"], "fg": CORES["texto_principal"], "anchor": "w"}
            prefixo_icone = "🔽" if escola == escola_expandida else "▶️"
            btn_escola = Button(frame_sidebar, text=f"{prefixo_icone} {escola}", **btn_escola_style, command=lambda e=escola: handle_clique_escola(e))
            btn_escola.pack(pady=2, fill="x")

            if escola == escola_selecionada: btn_escola.config(font=("Segoe UI", 11, "bold"))

            if escola == escola_expandida:
                frame_gaveta = Frame(frame_sidebar, bg=CORES["fundo_sidebar"])
                frame_gaveta.pack(fill="x", padx=(20, 0))

                turmas = sorted(list(set(a.get('name') for a in TODOS_OS_ALUNOS if a.get('descescola') == escola and a.get('name'))))
                
                btn_todas_style = {"font": ("Segoe UI", 10), "width": 20, "pady": 5, "relief": "flat", "bg": CORES["fundo_sidebar"], "fg": CORES["texto_principal"], "anchor": "w"}
                btn_todas = Button(frame_gaveta, text="Todas as Turmas", **btn_todas_style, command=lambda e=escola: handle_clique_turma(e, None))
                btn_todas.pack(pady=1, fill="x")
                if turma_selecionada is None: btn_todas.config(bg=CORES["destaque_turma"], fg=CORES["texto_destaque"])

                for turma in turmas:
                    btn_turma_style = {"font": ("Segoe UI", 10), "width": 20, "pady": 5, "relief": "flat", "bg": CORES["fundo_sidebar"], "fg": CORES["texto_principal"], "anchor": "w"}
                    btn_turma = Button(frame_gaveta, text=turma, **btn_turma_style, command=lambda e=escola, t=turma: handle_clique_turma(e, t))
                    btn_turma.pack(pady=1, fill="x")
                    if turma == turma_selecionada: btn_turma.config(bg=CORES["destaque_turma"], fg=CORES["texto_destaque"])

    def handle_clique_escola(escola_clicada):
        global escola_selecionada, turma_selecionada, escola_expandida
        
        if escola_clicada and escola_clicada == escola_expandida:
            escola_expandida = None 
        else:
            escola_expandida = escola_clicada
        
        escola_selecionada = escola_clicada
        turma_selecionada = None 
        
        redesenhar_sidebar()
        atualizar_lista_alunos()

    def handle_clique_turma(escola, turma):
        global turma_selecionada
        turma_selecionada = turma
        redesenhar_sidebar()
        atualizar_lista_alunos()

    frame_botoes = Frame(frame_form, bg=CORES["fundo_form"])
    frame_botoes.grid(row=len(labels_map)+2, column=0, columnspan=2, pady=30)
    btn_style = {"font": ("Segoe UI", 11, "bold"), "relief": "flat", "pady": 8, "padx": 15, "width": 18}
    Button(frame_botoes, text="ADICIONAR NOVO", command=lambda: adicionar_aluno(entries, root, atualizar_lista_alunos, redesenhar_sidebar), bg=CORES["botao_sucesso"], fg="white", **btn_style).pack(pady=5)
    Button(frame_botoes, text="SALVAR EDIÇÃO", command=lambda: editar_aluno(entries, user_listbox, root, atualizar_lista_alunos, redesenhar_sidebar), bg=CORES["botao_alerta"], fg=CORES["texto_alerta"], **btn_style).pack(pady=5)
    Button(frame_botoes, text="REMOVER SELECIONADO", command=lambda: remover_aluno(user_listbox, root, atualizar_lista_alunos, redesenhar_sidebar), bg=CORES["botao_perigo"], fg="white", **btn_style).pack(pady=5)
    Button(frame_botoes, text="LIMPAR CAMPOS", command=limpar_campos, bg=CORES["botao_limpar"], fg="white", **btn_style).pack(pady=5)

    if conectar_planilha():
        carregar_dados_da_planilha()
        handle_clique_escola(None)
        root.mainloop()
    else:
        root.destroy()
        
if __name__ == "__main__":
    criar_interface_crud()