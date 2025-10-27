# Agente Avaliador de QI (Flask)

Aplicativo de exemplo para avaliação adaptativa de QI usando Flask, matplotlib e fpdf.

Requisitos:
- Python 3.8+
- Instalar dependências: pip install -r requirements.txt

Executar:
- export FLASK_APP=app.py
- flask run

Arquivos importantes:
- app.py: backend Flask
- templates/: templates HTML (Bootstrap CDN)
- data/questions.json: banco de perguntas (preencha com mais questões)
- data/results.json: histórico local (salvo automaticamente)

Funcionalidades:
- Login leve (nome + PIN)
- Quiz adaptativo por nível (básico, intermediário, avançado)
- Armazenamento local em JSON
- Geração de gráfico de evolução com matplotlib
- Exportar relatório em PDF com fpdf
