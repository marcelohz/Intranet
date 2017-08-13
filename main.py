from flask import Flask, render_template, request, redirect
import psycopg2
app = Flask(__name__)

conn = psycopg2.connect("host=localhost dbname=intranet password=master user=postgres")

@app.route('/')
def hello_world():
    return render_template('index.html')


@app.route('/albuns')
def albuns():
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM intranet.album;")
    albuns = cur.fetchall()
    cur.close()
    return render_template('albuns.html', albuns=albuns)


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
    cur.execute("SELECT arquivo FROM intranet.foto where album_id = %s;", (id,))
    fotos = cur.fetchall()
    cur.close()

    return render_template('fotos.html', fotos = fotos)

if __name__ == '__main__':
    app.run()
