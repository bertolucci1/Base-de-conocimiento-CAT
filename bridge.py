import subprocess
import json
import re
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Permite que el index.html (frontend) pueda llamar a esta API sin problemas de origen

@app.route('/api/ad/user/<username>', methods=['GET'])
def get_ad_user(username):
    try:
        data = {
            "Username": username,
            "AD_Diagnostic": []
        }
        
        # 1. Obtener todos los datos clásicos del usuario (como net user)
        result_net = subprocess.run(["net", "user", username, "/domain"], capture_output=True, text=True, errors='replace')
        
        if result_net.returncode == 0:
            data["Entorno"] = "Active Directory"
            for line in result_net.stdout.split('\n'):
                if len(line) > 29:
                    key = line[:29].strip()
                    val = line[29:].strip()
                    if key and not key.startswith("The command") and not key.startswith("El comando se complet"):
                        data[key] = val
        else:
            # Fallback a usuario local
            res_local = subprocess.run(["net", "user", username], capture_output=True, text=True, errors='replace')
            if res_local.returncode == 0:
                data["Entorno"] = "PC Local (Fallback)"
                for line in res_local.stdout.split('\n'):
                    if len(line) > 29:
                        k = line[:29].strip()
                        v = line[29:].strip()
                        if k and not k.startswith("The command") and not k.startswith("El comando se complet"):
                            data[k] = v
            else:
                data["AD_Diagnostic"].append("Aviso: Falló la consulta nativa de 'net user'.")

        # 2. Extraer "Notas" (info) mediante PowerShell (ADSI) SIEMPRE (Ignorando fallos de red)
        ps_cmd = (
            f"$ErrorActionPreference = 'Stop'; "
            f"try {{ "
            f"    $searcher = [adsisearcher]\"(sAMAccountName={username})\"; "
            f"    $searcher.PropertiesToLoad.Add('info') | Out-Null; "
            f"    $searcher.PropertiesToLoad.Add('telephonenumber') | Out-Null; "
            f"    $user = $searcher.FindOne(); "
            f"    if ($user) {{ "
            f"        $info = $user.Properties['info'] -join ' | '; "
            f"        $tel = $user.Properties['telephonenumber'] -join ' | '; "
            f"        @{{ info = $info; telephoneNumber = $tel }} | ConvertTo-Json -Compress; "
            f"    }} else {{ Write-Output 'NO_USER' }} "
            f"}} catch {{ "
            f"    Write-Output \"PS_ERROR: $_\" "
            f"}}"
        )
        
        result_ps = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd], capture_output=True, text=True, errors='replace')

        out_str = result_ps.stdout.strip()
        err_str = result_ps.stderr.strip()

        if err_str:
            data["AD_Diagnostic"].append(f"Aviso (STDERR): {err_str}")

        if not out_str:
            data["AD_Diagnostic"].append("Error: PowerShell no devolvió ningún resultado (Salida vacía).")
        elif "PS_ERROR:" in out_str:
            data["AD_Diagnostic"].append(f"Error de PowerShell: {out_str}")
        elif out_str == "NO_USER":
            data["AD_Diagnostic"].append("ADSI: Usuario no encontrado en LDAP.")
        else:
            if "{" in out_str and "}" in out_str:
                out_str = out_str[out_str.find("{"):out_str.rfind("}")+1]
            if out_str:
                try:
                    ad_data = json.loads(out_str)
                    if isinstance(ad_data, dict):
                        if ad_data.get("telephoneNumber"):
                            data["Teléfono"] = ad_data["telephoneNumber"]
                        info_text = ad_data.get("info")
                        if info_text:
                            data["Notas AD (Directo)"] = info_text
                            # Regex Ultra flexible
                            match = re.search(r"(?:(\d{1,4}[-/]\d{1,2}[-/]\d{1,4}[ \t]+\d{1,2}:\d{1,2}:\d{1,2})\s*(?:at|en)?\s*)?(LOG\s*ON|LOG\s*OFF|INICI|CIERR)\s*(?:to|en|:|-)?\s*([A-Za-z0-9\-_]{3,})", info_text, re.IGNORECASE)
                            if match:
                                data["AD_Diagnostic"].append("Éxito: Regex detectó formato de log de sesión.")
                                data["RawLog"] = match.group(0)
                                if match.group(1):
                                    data["LastDate"] = match.group(1)
                                raw_action = match.group(2).upper().replace(" ", "")
                                data["LastAction"] = "LOGON" if "ON" in raw_action or "INICI" in raw_action else "LOGOFF"
                                data["LastPC"] = match.group(3).upper()
                            else:
                                data["AD_Diagnostic"].append("Aviso: Hay notas pero no coincidieron con la regla Regex. Se mostrará en crudo.")
                        else:
                            data["AD_Diagnostic"].append("Aviso: El campo 'Notas' está vacío en el Active Directory.")
                    else:
                        data["AD_Diagnostic"].append("Error: PowerShell devolvió un JSON que no es un diccionario.")
                except json.JSONDecodeError:
                    data["AD_Diagnostic"].append(f"Error al decodificar JSON. Salida de PS: {out_str}")

        return jsonify(data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)