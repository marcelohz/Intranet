import os
import random
import string
import psycopg2
from flask import Flask, session, redirect, url_for, request, send_from_directory
from flask import render_template, flash
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app = Flask(__name__)
UPLOAD_FOLDER = app.root_path + '/static/pix/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = os.urandom(16)
app.config.from_object(__name__)

conn = psycopg2.connect("host=localhost dbname=intranet password=master user=postgres")

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/favicon.ico')
def favicon():
    request
    return send_from_directory(app.root_path, 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/')
def index():
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For')
    else:
        ip = request.remote_addr

    usuario = pega_login(ip)
    return render_template('index.html', usuario=usuario, req=request.remote_addr)

def registra_login(user, ip):
    cur = conn.cursor()
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For')
    cur.execute("delete from intranet.login where ip = %s;", (ip,))
    cur.execute("INSERT INTO intranet.login(nome, ip) VALUES(%s, %s);", (user,ip))
    conn.commit()
    cur.close()

def pega_login(ip):
    if request.headers.get('X-Forwarded-For'):
        ip = request.headers.get('X-Forwarded-For')
    cur = conn.cursor()
    cur.execute("select nome from intranet.login where ip = %s;", (ip,))
    usuario = cur.fetchone()[0]
    cur.close()
    session['login'] = { ip: usuario }
    return usuario



@app.route('/registra_user/<user>')
def registra_user(user):
    registra_login(user, request.remote_addr)
    session['login'] = { request.remote_addr : user }
    return render_template('index.html', usuario=user)


@app.route('/logout')
def logout():
    session['admin'] = None
    return redirect('/')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    else:
        user = str(request.form.get('user'))
        password = str(request.form.get('password'))
        ip = request.remote_addr
        cur = conn.cursor()
        cur.execute("SELECT intranet.autentica(%s, %s, %s);", (user, password, ip))
        result = cur.fetchone()
        conn.commit()  # commitamos o insert que existe na função autentica
        cur.close()
        if result[0] is True:
            session['admin'] = user
            return render_template('index.html')
        else:
            flash(u'Usuário ou senha inválida')
        return render_template('login.html')


@app.route('/foto_upload', methods=['GET', 'POST'])
def foto_upload():
    if request.method == 'POST':
        album_id = str(request.form.get('album_id'))
        file = request.files['upload']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # filename = secrets.token_hex(8) + "." + filename.rsplit('.', 1)[1].lower()
            rnd = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(8)])
            filename = rnd + "." + filename.rsplit('.', 1)[1].lower()
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            cur = conn.cursor()
            cur.execute('INSERT INTO intranet.foto (album_id, arquivo) VALUES (%s, %s);', (album_id, filename))
            conn.commit()
            cur.close()
        return redirect(url_for('fotos', id=album_id))


@app.route('/albuns')
def albuns():
    cur = conn.cursor()
    cur.execute('SELECT id, nome FROM intranet.album;')
    albs = cur.fetchall()
    cur.close()
    return render_template('albuns.html', albuns=albs)


@app.route('/add_album', methods=['POST'])
def add_album():
    album = str(request.form.get('album'))
    cur = conn.cursor()
    cur.execute("INSERT INTO intranet.album(nome) VALUES(%s);", (album,))
    conn.commit()
    cur.close()
    return redirect("/albuns")


@app.route('/fotos/<id>')
def fotos(id):
    cur = conn.cursor()
    cur.execute(
        'SELECT arquivo, nome FROM intranet.foto, intranet.album WHERE foto.album_id = album.id AND album_id = %s;',
        (id,))
    fotos = cur.fetchall()
    cur.close()
    return render_template('fotos.html', fotos=fotos, album_id=id)


@app.route('/del_foto/<arquivo>')
def del_foto(arquivo):
    if session['admin'] is None:
        return redirect(404)

    # primeiro pegamos o album pra saber pra onde voltar
    sql = 'SELECT album_id FROM intranet.album, intranet.foto WHERE album.id = foto.album_id AND foto.arquivo = %s'
    cur = conn.cursor()
    cur.execute(sql, (arquivo,))
    album_id = str(cur.fetchone()[0])

    sql = 'DELETE FROM intranet.foto WHERE arquivo = %s'
    cur.execute(sql, (arquivo,))
    conn.commit()
    cur.close()
    os.remove(app.root_path + '/static/pix/' + arquivo)
    return redirect('/fotos/' + album_id)


@app.route('/busca_ramal', methods=['POST'])
def busca_ramal():
    sql = '''
      SELECT DISTINCT setor.nome, string_agg(DISTINCT funcionario.nome, ', '), string_agg(DISTINCT numero, ', ') 
        FROM intranet.setor, intranet.funcionario, intranet.ramal
        WHERE funcionario.setor_id = setor.id AND ramal.setor_id = setor.id AND funcionario.nome ILIKE %s 
        GROUP BY setor.nome
    '''
    query = request.form.get('query')
    cur = conn.cursor()
    cur.execute(sql, ('%' + query + '%',))
    ramais = cur.fetchall()
    cur.close()
    return render_template('busca_ramal.html', ramais=ramais)


@app.route('/add_ramal', methods=['POST'])
def add_ramal():
    cur = conn.cursor()
    sql = 'SELECT setor.id FROM intranet.setor WHERE nome = upper(%s)'
    cur.execute(sql, (request.form.get('setor'),))
    setor_id = cur.fetchone()
    if setor_id is None:
        flash('Setor inexistente.', 'error')
        return redirect("/ramais")

    sql = 'INSERT INTO intranet.ramal (numero, setor_id) VALUES (%s, %s) RETURNING *;'
    cur.execute(sql, (request.form.get("numero"), setor_id))
    conn.commit()
    test = cur.fetchone()
    cur.close()
    if test is not None:
        flash('Ramal cadastrado.', 'success')
    return redirect("/ramais")


@app.route('/ramais')
def ramais():
    cur = conn.cursor()

    sql = '''SELECT setor.nome, numero, ramal.id FROM intranet.setor, intranet.ramal
          WHERE ramal.setor_id = setor.id
          ORDER BY setor.nome
        '''
    cur.execute(sql)
    ramais = cur.fetchall()
    cur.close()

    return render_template('ramais.html', ramais=ramais)


@app.route('/del_ramal/<id>')
def del_ramal(id):
    if session['admin'] is None:
        return redirect(404)
    cur = conn.cursor()
    cur.execute('DELETE FROM intranet.ramal WHERE id = %s;', (id,))
    conn.commit()
    flash('Ramal excluído', 'success')
    return redirect('/ramais')


@app.route('/del_func/<id>')
def del_func(id):
    if session['admin'] is None:
        return redirect(404)
    cur = conn.cursor()
    cur.execute('DELETE FROM intranet.funcionario WHERE id = %s;', (id,))
    conn.commit()
    flash('Funcionário excluído', 'success')
    return redirect('/funcionarios')


@app.route('/funcionarios', methods=['GET', 'POST'])
def funcionarios():
    sql = "SELECT id, nome FROM intranet.setor ORDER BY nome"
    cur = conn.cursor()
    cur.execute(sql)
    setores = cur.fetchall()
    cur.close()

    sql = '''SELECT funcionario.id, funcionario.nome, setor.id, setor.nome FROM intranet.setor, 
            intranet.funcionario WHERE funcionario.setor_id = setor.id
          '''
    cur = conn.cursor()
    cur.execute(sql)
    funcsets = [dict(func_id=r[0], func_nome=r[1], setor_id=r[2], setor_nome=r[3]) for r in cur.fetchall()]
    cur.close()

    if request.method == 'POST':
        sql = 'INSERT INTO intranet.funcionario(nome, setor_id) VALUES(%s, %s)'
        cur = conn.cursor()
        cur.execute(sql, (request.form.get('nome'), request.form.get('setor_id')))
        conn.commit()
        cur.close()
        flash('Funcionário cadastrado.', 'success')
        return redirect('/funcionarios')
    return render_template('funcionarios.html', setores=setores, funcsets=funcsets)


@app.errorhandler(404)
def not_found(error):
    return 'URL inexiste. 404.', 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('fatal.html', msg=error)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
