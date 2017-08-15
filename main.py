import os

import secrets

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
    return send_from_directory(app.root_path, 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/')
def hello_world():
    session['usuario'] = None
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    else:
        user = str(request.form.get('user'))
        password = str(request.form.get('password'))
        ip = request.remote_addr
        hostname = request.host
        cur = conn.cursor()
        cur.execute("SELECT intranet.autentica(%s, %s, %s, %s);", (user, password, ip, hostname))
        result = cur.fetchone()
        cur.close()
        if result[0] is True:
            session['usuario'] = user
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
            filename = secrets.token_hex(8) + "." + filename.rsplit('.', 1)[1].lower()
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            cur = conn.cursor()
            cur.execute("insert into intranet.foto (album_id, arquivo) values (%s, %s);", (album_id, filename))
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
    cur.execute("insert into intranet.album(nome) values(%s);", (album,))
    conn.commit()
    cur.close()
    return redirect("/albuns")


@app.route('/fotos/<id>')
def fotos(id):
    cur = conn.cursor()
    cur.execute('SELECT arquivo, nome FROM intranet.foto, intranet.album where foto.album_id = album.id and album_id = %s;', (id,))
    fotos = cur.fetchall()
    cur.close()
    return render_template('fotos.html', fotos=fotos, album_id=id)


@app.route('/del_foto/<arquivo>')
def del_foto(arquivo):
    if session['usuario'] is None:
        return redirect(404)
    sql = 'delete from intranet.foto where arquivo = %s'
    cur = conn.cursor()
    cur.execute(sql, (arquivo,))
    conn.commit()
    cur.close()
    os.remove(app.root_path + '/static/pix/' + arquivo)


@app.route('/busca_ramal', methods=['POST'])
def busca_ramal():
    sql = '''
      SELECT distinct setor.nome, string_agg(distinct funcionario.nome, ', '), string_agg(distinct numero, ', ') from intranet.setor, intranet.funcionario, intranet.ramal
          where funcionario.setor_id = setor.id and ramal.setor_id = setor.id and funcionario.nome ilike %s group by setor.nome
    '''
    query = request.form.get('query')
    cur = conn.cursor()
    cur.execute(sql, ('%' + query +'%',))
    ramais = cur.fetchall()
    cur.close()
    return render_template('busca_ramal.html', ramais = ramais)


@app.route('/add_ramal', methods=['POST'])
def add_ramal():
    cur = conn.cursor()
    sql = 'SELECT setor.id from intranet.setor where nome = upper(%s)'
    cur.execute(sql, (request.form.get('setor'),))
    setor_id = cur.fetchone()
    if setor_id is None:
        flash('Setor inexistente.', 'error')
        return redirect("/ramais")

    sql = 'insert into intranet.ramal (numero, setor_id) values (%s, %s) RETURNING *;'
    cur.execute(sql, (request.form.get("numero"), setor_id))
    conn.commit()
    test = cur.fetchone()
    cur.close()
    if test != None:
        flash('Ramal adicionado.', 'info')
    return redirect("/ramais")


@app.route('/ramais')
def ramais():
    cur = conn.cursor()

    sql = '''SELECT setor.nome, numero from intranet.setor, intranet.ramal
          where ramal.setor_id = setor.id
          order by setor.nome
        '''
    cur.execute(sql)
    ramais = cur.fetchall()
    cur.close()

    return render_template('ramais.html', ramais = ramais)


@app.route('/del_func/<id>')
def del_func(id):
    if session['usuario'] is None:
        return redirect(404)
    cur = conn.cursor()
    cur.execute('delete from intranet.funcionario where id = %s;', (id,))
    conn.commit()
    flash('Funcionário excluído', 'info')
    return redirect('/funcionarios')


@app.route('/funcionarios', methods=['GET', 'POST'])
def funcionarios():
    sql = "select id, nome from intranet.setor order by nome"
    cur = conn.cursor()
    cur.execute(sql)
    setores = cur.fetchall()
    cur.close()

    sql = 'select funcionario.id, funcionario.nome, setor.id, setor.nome from intranet.setor, intranet.funcionario where funcionario.setor_id = setor.id'
    cur = conn.cursor()
    cur.execute(sql)
    funcsets = [dict(func_id=r[0], func_nome=r[1], setor_id=r[2], setor_nome=r[3]) for r in cur.fetchall()]
    cur.close()

    if request.method == 'POST':
        sql = 'insert into intranet.funcionario(nome, setor_id) values(%s, %s)'
        cur = conn.cursor()
        cur.execute(sql, (request.form.get('nome'), request.form.get('setor_id')))
        conn.commit()
        cur.close()
        flash('Funcionário cadastrado.', 'info')
        return redirect('/funcionarios')
    return render_template('funcionarios.html', setores=setores, funcsets=funcsets)


@app.errorhandler(404)
def not_found(error):
    return 'URL inexiste. 404.', 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('fatal.html', msg=error)


if __name__ == '__main__':
    app.run()
