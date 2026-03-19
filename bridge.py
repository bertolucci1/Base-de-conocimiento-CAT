import subprocess
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Permite que el index.html (frontend) pueda llamar a esta API sin problemas de origen

@app.route('/api/ad/user/<username>', methods=['GET'])
def get_ad_user(username):
    try:
        # Ejecutamos el comando de Windows: net user <username> /domain
        # capture_output y text permiten capturar el resultado como string, usamos errors='replace' por si hay acentos.
        result = subprocess.run(["net", "user", username, "/domain"], capture_output=True, text=True, errors='replace')
        
        if result.returncode != 0:
            # Si falla, devolvemos el error de la terminal
            error_msg = result.stderr.strip() or "Usuario no encontrado en el dominio."
            return jsonify({"error": f"Error AD: {error_msg}"}), 404

        lines = result.stdout.split('\n')
        data = {"Username": username}
        
        # Parsear (limpiar) la salida de la terminal
        # El comando 'net user' siempre divide la Clave del Valor alineándolo en el carácter/columna 29
        for line in lines:
            if len(line) > 29:
                key = line[:29].strip()
                val = line[29:].strip()
                
                # Ignoramos líneas vacías o de mensajes del sistema
                if key and not key.startswith("The command") and not key.startswith("El comando se complet"):
                    data[key] = val
                    
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)