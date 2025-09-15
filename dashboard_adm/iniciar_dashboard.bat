@echo off
TITLE Dashboard de Monitoramento
echo Desenvolvido por Alan Mathias
echo Contato: alanmathiasctt@gmail.com
echo.
echo ========================================================
echo   INICIANDO O SERVIDOR DO DASHBOARD DE MONITORAMENTO
echo ========================================================
echo.
echo Isso pode levar alguns segundos...
echo O dashboard abrira automaticamente no seu navegador.
echo.
echo ESTA JANELA DEVE PERMANECER ABERTA.
echo Para encerrar o dashboard, basta fechar esta janela.
echo.
REM Executa o Streamlit usando o Python que esta nesta pasta
python\python.exe -m streamlit run dashboard_adm.py --server.headless true
pause