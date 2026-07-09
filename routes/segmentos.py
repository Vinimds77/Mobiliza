@app.route("/campanhas", methods=["GET", "POST"])
def campanhas():

    if request.method == "POST":

        codigo = secrets.token_hex(3)

        campanha = Campanha(
            titulo=request.form["titulo"],
            destino=request.form["destino"],
            codigo=codigo
        )

        db.session.add(campanha)
        db.session.commit()

        return f"""
        <h2>Campanha criada!</h2>

        <p>Seu link:</p>

        <h3>
        http://127.0.0.1:5000/r/{codigo}
        </h3>

        <a href="/campanhas">
            Criar outra campanha
        </a>
        """

    return render_template("campanhas.html")