import subprocess
import json
import re
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Permite que el index.html (frontend) pueda llamar a esta API sin problemas de origen

def run_ps(script):
    """Ejecuta un script de PowerShell de forma segura pasándolo por entrada estándar (stdin)."""
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", "-"],
        input=script,
        capture_output=True,
        text=True,
        errors='replace'
    )

def normalize_account_status(value):
    """
    Normaliza el campo 'Cuenta activa' a un booleano.
    Retorna True si la cuenta está activa, False si está deshabilitada.
    """
    if not value:
        return None
    
    val_clean = str(value).strip().lower()
    # En español: "Sí", "SI", "SÍ", "S¡" → True
    # En inglés: "Yes", "Y" → True
    # En español: "No", "No" → False
    # En inglés: "No" → False
    
    if val_clean.startswith('s') or val_clean.startswith('y'):
        return True
    elif val_clean.startswith('n'):
        return False
    
    return None

def get_ad_credentials():
    """Extrae las credenciales AD de los headers y crea el bloque de autenticación PS."""
    ad_user = request.headers.get('X-AD-User', '')
    ad_pass = request.headers.get('X-AD-Pass', '')
    if ad_user and ad_pass:
        safe_user = ad_user.replace("'", "''")
        safe_pass = ad_pass.replace("'", "''")
        cred_block = f"$secPass = ConvertTo-SecureString '{safe_pass}' -AsPlainText -Force;\n$cred = New-Object System.Management.Automation.PSCredential ('CATMAIN\\{safe_user}', $secPass);\n"
        return cred_block, "-Credential $cred"
    return "", ""

@app.route('/api/ad/user/<username>', methods=['GET', 'OPTIONS'])
def get_ad_user(username):
    if request.method == 'OPTIONS': return jsonify({"status": "ok"}), 200
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
            
            # Procesar y normalizar el campo "Cuenta activa"
            if "Cuenta activa" in data:
                account_status = normalize_account_status(data["Cuenta activa"])
                if account_status is not None:
                    data["account_active"] = account_status  # Booleano normalizado
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
                
                # Procesar y normalizar el campo "Cuenta activa" en fallback local
                if "Cuenta activa" in data:
                    account_status = normalize_account_status(data["Cuenta activa"])
                    if account_status is not None:
                        data["account_active"] = account_status  # Booleano normalizado
            else:
                data["AD_Diagnostic"].append("Aviso: Falló la consulta nativa de 'net user'.")

        cred_block, cred_param = get_ad_credentials()
        
        ps_script = f"""
        $ErrorActionPreference = 'Stop'
        try {{
            {cred_block}
            if ($cred) {{
                $domain = [System.DirectoryServices.ActiveDirectory.Domain]::GetCurrentDomain().Name
                $rootEntry = New-Object System.DirectoryServices.DirectoryEntry("LDAP://$domain", $cred.UserName, $cred.GetNetworkCredential().Password)
                $searcher = New-Object System.DirectoryServices.DirectorySearcher($rootEntry)
            }} else {{
                $searcher = [adsisearcher]""
            }}
            $searcher.Filter = "(sAMAccountName={username})"
            $searcher.PropertiesToLoad.Add('info') | Out-Null
            $searcher.PropertiesToLoad.Add('telephonenumber') | Out-Null
            $searcher.PropertiesToLoad.Add('displayname') | Out-Null
            $searcher.PropertiesToLoad.Add('name') | Out-Null
            $user = $searcher.FindOne()
            if ($user) {{
                $info = $user.Properties['info'] -join ' | '
                $tel = $user.Properties['telephonenumber'] -join ' | '
                $displayname = $user.Properties['displayname'] -join ' | '
                $name = $user.Properties['name'] -join ' | '
                @{{ info = $info; telephoneNumber = $tel; displayName = $displayname; name = $name }} | ConvertTo-Json -Compress
            }} else {{ Write-Output 'NO_USER' }}
        }} catch {{ Write-Output "PS_ERROR: $_" }}
        """
        result_ps = run_ps(ps_script)

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
                        if ad_data.get("displayName"):
                            data["Nombre Completo"] = ad_data["displayName"]
                        elif ad_data.get("name"):
                            data["Nombre Completo"] = ad_data["name"]
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

@app.route('/api/ping', methods=['GET'])
def ping_api():
    return jsonify({"status": "ok", "message": "AD Bridge en linea"})

@app.route('/api/tickets/test_self', methods=['POST'])
def test_ticketera_self():
    try:
        load_dotenv()
        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")

        if not all([smtp_server, smtp_user, smtp_password]):
            return jsonify({"status": "error", "message": "Faltan credenciales SMTP en el entorno (.env)."}), 500

        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = "TKHELPDESKBA@cat-technologies.com"
        msg['Subject'] = "TEST TICKETERA - Diagnóstico BDC (Prueba Interna)"

        body = "Esta es una prueba de correo generada automáticamente desde el módulo de diagnóstico de la Base de Conocimiento (CAT BDC HELPDESK)."
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()

        return jsonify({"status": "success", "message": "Correo de prueba enviado con éxito a TKHELPDESKBA@cat-technologies.com"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al enviar correo: {str(e)}"}), 500

@app.route('/api/ad/reset-token', methods=['POST', 'OPTIONS'])
def reset_vpn_token():
    if request.method == 'OPTIONS': return jsonify({"status": "ok"}), 200
    try:
        payload = request.json
        username = payload.get('username')

        if not username:
            return jsonify({"status": "error", "message": "No se proporcionó el nombre de usuario."}), 400

        cred_block, cred_param = get_ad_credentials()

        ps_script = f"""
        $ErrorActionPreference = 'Stop'
        try {{
            {cred_block}
            Invoke-Command -ComputerName BMWINRAP.CATMAIN.LOCAL {cred_param} -ScriptBlock {{ param($user) C:\\Scripts\\BorraTokenService.ps1 -Username $user }} -ArgumentList '{username}'
            Write-Output 'TOKEN_RESET_SUCCESS'
        }} catch {{
            Write-Output "PS_ERROR: $_"
        }}
        """
        result_ps = run_ps(ps_script)
        
        output = result_ps.stdout.strip()
        error_output = result_ps.stderr.strip()

        if result_ps.returncode != 0 or "PS_ERROR:" in output or error_output:
            error_message = output if "PS_ERROR:" in output else (error_output or output)
            return jsonify({"status": "error", "message": f"Error en PowerShell: {error_message}"}), 500
        
        return jsonify({"status": "success", "message": f"Token VPN para {username} restablecido con éxito."})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/ad/computer/<ws_name>', methods=['GET', 'OPTIONS'])
def get_ad_computer(ws_name):
    if request.method == 'OPTIONS': return jsonify({"status": "ok"}), 200
    try:
        cred_block, cred_param = get_ad_credentials()
        ps_script = f"""
        $ErrorActionPreference = 'Stop'
        {cred_block}
        Get-ADComputer -Identity '{ws_name}' -Properties DistinguishedName {cred_param} | Select-Object -ExpandProperty DistinguishedName
        """
        result = run_ps(ps_script)
        out = result.stdout.strip()
        
        if result.returncode != 0 or not out:
            return jsonify({"status": "error", "message": f"No se encontró el equipo '{ws_name}' en el dominio."}), 404
        
        dn_parts = out.split(',')
        ou_path = ','.join(dn_parts[1:]) if len(dn_parts) > 1 else out

        return jsonify({"status": "success", "ws_name": ws_name, "distinguishedName": out, "ou_path": ou_path})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/ad/computer/remove', methods=['POST', 'OPTIONS'])
def remove_ad_computer():
    if request.method == 'OPTIONS': return jsonify({"status": "ok"}), 200
    try:
        ws_name = request.json.get('ws_name')
        if not ws_name:
            return jsonify({"status": "error", "message": "No se proporcionó el nombre del equipo."}), 400

        cred_block, cred_param = get_ad_credentials()
        ps_script = f"""
        $ErrorActionPreference = 'SilentlyContinue'
        {cred_block}
        $computerAccount = '{ws_name}$'
        $domainControllers = Get-ADDomainController -Filter * {cred_param}
        foreach ($dc in $domainControllers) {{
            Remove-ADComputer -Identity $computerAccount -Server $dc.HostName -Confirm:$false {cred_param}
        }}
        Write-Output 'SUCCESS'
        """
        run_ps(ps_script)
        return jsonify({"status": "success", "message": f"Cuenta de equipo '{ws_name}' purgada de los Controladores de Dominio."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/ad/computer/prestage', methods=['POST', 'OPTIONS'])
def prestage_ad_computer():
    if request.method == 'OPTIONS': return jsonify({"status": "ok"}), 200
    try:
        ws_name = request.json.get('ws_name')
        ou_path = request.json.get('ou_path')
        if not ws_name or not ou_path:
            return jsonify({"status": "error", "message": "Faltan parámetros (Nombre de equipo o Ruta de OU)."}), 400

        cred_block, cred_param = get_ad_credentials()
        ps_script = f"""
        $ErrorActionPreference = 'Stop'
        try {{
            {cred_block}
            New-ADComputer -Name '{ws_name}' -Path '{ou_path}' {cred_param}
        }} catch {{ Write-Output "PS_ERROR: $_" }}
        """
        result = run_ps(ps_script)
        if "PS_ERROR:" in result.stdout or result.returncode != 0:
            err = result.stdout.strip() if "PS_ERROR:" in result.stdout else result.stderr.strip()
            return jsonify({"status": "error", "message": f"Fallo al pre-crear el equipo: {err}"}), 500
            
        return jsonify({"status": "success", "message": f"Equipo '{ws_name}' pre-creado exitosamente en su OU original."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/ad/reset_password/<username>', methods=['POST', 'OPTIONS'])
def reset_ad_password(username):
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
        
    try:
        payload = request.json
        new_password = payload.get('new_password', '')
        unlock_account = payload.get('unlock_account', False)
        change_next_logon = payload.get('change_next_logon', False)

        if not new_password:
            return jsonify({"error": "La contraseña no puede estar vacía"}), 400

        cred_block, cred_param = get_ad_credentials()
        safe_new_pass = new_password.replace("'", "''")

        ps_script = f"""
        $ErrorActionPreference = 'Stop'
        try {{
            {cred_block}
            $newSecPass = ConvertTo-SecureString '{safe_new_pass}' -AsPlainText -Force
            Set-ADAccountPassword -Identity '{username}' -NewPassword $newSecPass -Reset {cred_param}
        """
        if unlock_account:
            ps_script += f"\n    Unlock-ADAccount -Identity '{username}' {cred_param}"
        if change_next_logon:
            ps_script += f"\n    Set-ADUser -Identity '{username}' -ChangePasswordAtLogon $true {cred_param}"
        
        ps_script += """
            Write-Output 'SUCCESS'
        } catch { Write-Output "PS_ERROR: $_" }
        """
        
        result_ps = run_ps(ps_script)
        out = result_ps.stdout.strip()
        
        if "PS_ERROR:" in out or result_ps.returncode != 0:
            return jsonify({"error": f"Fallo al cambiar contraseña (Error de permisos o conexión): {out or result_ps.stderr}"}), 500

        messages = ["Contraseña actualizada de forma segura (PowerShell)."]
        if unlock_account: messages.append("Cuenta desbloqueada.")
        if change_next_logon: messages.append("Requerirá cambio en próximo inicio.")

        return jsonify({"message": " | ".join(messages)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)