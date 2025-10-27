from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
import json
import random
import os
from datetime import datetime
from io import BytesIO
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fpdf import FPDF

# Configuração
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'troque_esta_chave_para_producao')

DATA_DIR = 'data'
QUESTIONS_FILE = os.path.join(DATA_DIR, 'questions.json')
RESULTS_FILE = os.path.join(DATA_DIR, 'results.json')

# Parâmetros do quiz
NUM_QUESTIONS = 10  # número de perguntas por sessão
LEVELS = ['basico', 'intermediario', 'avancado']
LEVEL_WEIGHTS = {'basico': 0.9, 'intermediario': 1.0, 'avancado': 1.1}

# Helpers para arquivos JSON
def ensure_data_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(QUESTIONS_FILE):
        # criar arquivo vazio padrão (o usuário deverá preencher)
        with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "basico": [],
                "intermediario": [],
                "avancado": []
            }, f, ensure_ascii=False, indent=2)
    if not os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

def load_questions():
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_results():
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_results(data):
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Lógica adaptativa: escolhe próximo nível
def next_level(current_level, correct, streak):
    idx = LEVELS.index(current_level)
    if correct:
        # se acerto e streak positivo, sobe de nível
        if streak >= 1 and idx < len(LEVELS) - 1:
            return LEVELS[idx + 1]
        return current_level
    else:
        # se erro, desce de nível
        if idx > 0:
            return LEVELS[idx - 1]
        return current_level

# Seleciona uma pergunta aleatória de um nível, evitando duplicados
def select_question(questions_bank, level, used_ids):
    pool = [q for q in questions_bank.get(level, []) if q.get('id') not in used_ids]
    if not pool:
        # se esgotou, permita repetir
        pool = questions_bank.get(level, [])[:]
    if not pool:
        return None
    return random.choice(pool)

# Calcula IQ estimado
def estimate_iq(answers):
    if not answers:
        return 85
    total = len(answers)
    weighted_correct = 0.0
    for a in answers:
        if a['correct']:
            weighted_correct += LEVEL_WEIGHTS.get(a['level'], 1.0)
    # IQ escala entre ~70 e ~130 dependendo da performance ponderada
    score_ratio = weighted_correct / total  # 0..2 (approx)
    iq = round(80 + score_ratio * 45)  # ajustável
    if iq < 60: iq = 60
    if iq > 160: iq = 160
    return iq

# Sugestão personalizada baseada no IQ
def suggestion_for_iq(iq):
    if iq < 90:
        return "Reforce lógica básica: pratique séries, padrões e raciocínio passo a passo."
    if iq < 110:
        return "Boa base. Trabalhe em questões de raciocínio intermediário para ganhar velocidade."
    return "Ótimo desempenho! Tente desafios complexos e problemas de múltiplas etapas."

# Rotas
@app.route('/', methods=['GET', 'POST'])
def index():
    # Autenticação leve: nome + PIN
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        pin = request.form.get('pin', '').strip()
        if not name or not pin:
            flash('Por favor, preencha nome e PIN.', 'danger')
            return redirect(url_for('index'))
        # iniciar sessão
        session.clear()
        session['user'] = name
        session['pin'] = pin
        return redirect(url_for('start'))
    return render_template('index.html')

@app.route('/start')
def start():
    if 'user' not in session:
        return redirect(url_for('index'))
    # preparar sessão de quiz
    questions_bank = load_questions()
    session['current_level'] = 'intermediario'  # começa no nível intermediário
    session['used_ids'] = []
    session['answers'] = []
    session['q_index'] = 0
    session['streak'] = 0
    return redirect(url_for('question'))

@app.route('/question')
def question():
    if 'user' not in session:
        return redirect(url_for('index'))
    q_index = session.get('q_index', 0)
    if q_index >= NUM_QUESTIONS:
        return redirect(url_for('result'))
    questions_bank = load_questions()
    level = session.get('current_level', 'intermediario')
    used_ids = session.get('used_ids', [])
    q = select_question(questions_bank, level, used_ids)
    if q is None:
        flash('Sem perguntas disponíveis. Por favor, adicione perguntas ao arquivo data/questions.json', 'warning')
        return redirect(url_for('result'))
    session['current_question'] = q
    return render_template('question.html', question=q, index=q_index+1, total=NUM_QUESTIONS, level=level)

@app.route('/answer', methods=['POST'])
def answer():
    if 'user' not in session or 'current_question' not in session:
        return redirect(url_for('index'))
    chosen = request.form.get('option')
    q = session['current_question']
    correct_option = str(q.get('answer'))
    is_correct = (chosen == correct_option)
    # atualizar streak
    streak = session.get('streak', 0)
    if is_correct:
        streak = streak + 1
    else:
        streak = 0
    session['streak'] = streak
    # decidir próximo nível
    current_level = session.get('current_level', 'intermediario')
    next_lv = next_level(current_level, is_correct, streak)
    session['current_level'] = next_lv
    # registrar resposta
    answers = session.get('answers', [])
    answers.append({
        'question_id': q.get('id'),
        'text': q.get('text'),
        'selected': chosen,
        'correct': is_correct,
        'level': q.get('level', current_level),
        'options': q.get('options')
    })
    session['answers'] = answers
    used_ids = session.get('used_ids', [])
    used_ids.append(q.get('id'))
    session['used_ids'] = used_ids
    session['q_index'] = session.get('q_index', 0) + 1
    # seguir para próxima pergunta ou resultado
    if session['q_index'] >= NUM_QUESTIONS:
        return redirect(url_for('result'))
    return redirect(url_for('question'))

@app.route('/result')
def result():
    if 'user' not in session:
        return redirect(url_for('index'))
    answers = session.get('answers', [])
    total = len(answers)
    corrects = sum(1 for a in answers if a['correct'])
    iq = estimate_iq(answers)
    suggestion = suggestion_for_iq(iq)
    # salvar no histórico
    user = session.get('user')
    results = load_results()
    user_history = results.get(user, [])
    entry = {
        'date': datetime.utcnow().isoformat() + 'Z',
        'total': total,
        'correct': corrects,
        'iq': iq,
        'suggestion': suggestion,
        'answers': answers
    }
    user_history.append(entry)
    results[user] = user_history
    save_results(results)
    return render_template('result.html', entry=entry, user=user)

@app.route('/export_pdf')
def export_pdf():
    if 'user' not in session:
        return redirect(url_for('index'))
    answers = session.get('answers', [])
    total = len(answers)
    corrects = sum(1 for a in answers if a['correct'])
    iq = estimate_iq(answers)
    suggestion = suggestion_for_iq(iq)
    user = session.get('user')
    # gerar PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, f'Relatório de Avaliação de QI - {user}', ln=True)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f'Data (UTC): {datetime.utcnow().isoformat()}', ln=True)
    pdf.cell(0, 8, f'Pontuação: {corrects}/{total}', ln=True)
    pdf.cell(0, 8, f'IQ Estimado: {iq}', ln=True)
    pdf.multi_cell(0, 8, f'Sugestão: {suggestion}')
    pdf.ln(4)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Detalhes das respostas:', ln=True)
    pdf.set_font('Arial', '', 11)
    for i, a in enumerate(answers, 1):
        status = 'Correto' if a['correct'] else 'Errado'
        pdf.multi_cell(0, 7, f'{i}. ({a["level"]}) {a["text"]} -- {status}')
    # retornar PDF em memória
    mem = BytesIO()
    mem.write(pdf.output(dest='S').encode('latin-1'))
    mem.seek(0)
    return send_file(mem, as_attachment=True, download_name=f'relatorio_{user}_{datetime.utcnow().date()}.pdf', mimetype='application/pdf')

@app.route('/history')
def history():
    if 'user' not in session:
        return redirect(url_for('index'))
    user = session.get('user')
    results = load_results()
    user_history = results.get(user, [])
    return render_template('history.html', history=user_history, user=user)

@app.route('/history/plot.png')
def history_plot():
    if 'user' not in session:
        return redirect(url_for('index'))
    user = session.get('user')
    results = load_results()
    user_history = results.get(user, [])
    dates = [datetime.fromisoformat(e['date'].rstrip('Z')) for e in user_history]
    iqs = [e['iq'] for e in user_history]
    fig, ax = plt.subplots(figsize=(6,3))
    if dates:
        ax.plot(dates, iqs, marker='o', linestyle='-')
        ax.set_title('Evolução do IQ')
        ax.set_ylabel('IQ estimado')
        ax.set_ylim(min(50, min(iqs)-10), max(160, max(iqs)+10))
        fig.autofmt_xdate()
    else:
        ax.text(0.5, 0.5, 'Sem dados', ha='center', va='center')
        ax.set_axis_off()
    buf = BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

# Inicialização
if __name__ == '__main__':
    ensure_data_files()
    app.run(debug=True)
