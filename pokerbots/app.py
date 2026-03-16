'''
HopAI Pokerbots — Web Dashboard
Run with: python app.py [port]
Open: http://localhost:PORT
'''
import os
import sys
import re
import zipfile
import threading
import tempfile
import shutil

from flask import Flask, render_template, jsonify, request, abort

import database as db
import tournament as t

BOTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bots')
SKELETON_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'engine', 'python_skeleton', 'skeleton')
TEAM_NAME_RE = re.compile(r'^[a-zA-Z0-9_]{2,24}$')

app = Flask(__name__)

_tournament_thread = None
_tournament_lock = threading.Lock()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    db.init_db()
    leaderboard = [dict(r) for r in db.get_leaderboard()]
    matches = [dict(r) for r in db.get_matches(limit=20)]
    state = dict(db.get_tournament_state())
    bots = t.discover_bots()
    return render_template('index.html',
                           leaderboard=leaderboard,
                           matches=matches,
                           state=state,
                           bot_count=len(bots))


@app.route('/match/<int:match_id>')
def match_detail(match_id):
    match = db.get_match(match_id)
    if not match:
        abort(404)
    match = dict(match)

    log_content = None
    if match.get('log_path'):
        try:
            with open(match['log_path'] + '.txt', 'r') as f:
                log_content = f.read()
        except FileNotFoundError:
            pass

    return render_template('match.html', match=match, log_content=log_content)


# ── Submission ────────────────────────────────────────────────────────────────

@app.route('/submit')
def submit_page():
    bots = t.discover_bots()
    existing = [b['name'] for b in bots]
    return render_template('submit.html', existing_bots=existing)


@app.route('/api/submit', methods=['POST'])
def api_submit():
    team_name = request.form.get('team_name', '').strip()
    zip_file  = request.files.get('bot_zip')

    # Validate team name
    if not TEAM_NAME_RE.match(team_name):
        return jsonify({'error': 'Team name must be 2–24 characters: letters, numbers, underscores only.'}), 400

    # Blocked names (reserved sample bots)
    reserved = {'always_call', 'always_fold', 'aggressor', 'balanced', 'example_bot'}
    if team_name.lower() in reserved:
        return jsonify({'error': f'"{team_name}" is a reserved name. Choose a different team name.'}), 400

    if not zip_file or not zip_file.filename.endswith('.zip'):
        return jsonify({'error': 'Please upload a .zip file.'}), 400

    # Save zip to temp location and validate contents
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, 'bot.zip')
        zip_file.save(zip_path)

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                names = zf.namelist()

                # Guard against zip-slip path traversal
                for name in names:
                    if '..' in name or name.startswith('/'):
                        return jsonify({'error': 'Invalid zip: suspicious file paths.'}), 400

                # Only allow .py and .json files
                for name in names:
                    if not name.endswith(('.py', '.json', '/')):
                        return jsonify({'error': f'Invalid file in zip: {name}. Only .py and .json files allowed.'}), 400

                # Must contain player.py and commands.json at root (possibly in a subfolder)
                flat = [os.path.basename(n) for n in names]
                if 'player.py' not in flat:
                    return jsonify({'error': 'Zip must contain player.py'}), 400
                if 'commands.json' not in flat:
                    return jsonify({'error': 'Zip must contain commands.json'}), 400

                # Extract to temp dir, then move to bots/
                extract_dir = os.path.join(tmp, 'extracted')
                zf.extractall(extract_dir)

                # If everything is inside a single subfolder, unwrap it
                entries = os.listdir(extract_dir)
                if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
                    extract_dir = os.path.join(extract_dir, entries[0])

        except zipfile.BadZipFile:
            return jsonify({'error': 'Could not read zip file. Make sure it is a valid .zip.'}), 400

        # Install to bots/<team_name>/
        dest = os.path.join(BOTS_DIR, team_name)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(extract_dir, dest)

    # Add skeleton symlink so bot can import it
    skeleton_link = os.path.join(dest, 'skeleton')
    if not os.path.exists(skeleton_link):
        os.symlink(SKELETON_SRC, skeleton_link)

    return jsonify({'status': 'ok', 'team': team_name})


# ── API ───────────────────────────────────────────────────────────────────────

@app.route('/api/status')
def api_status():
    state = dict(db.get_tournament_state())
    leaderboard = [dict(r) for r in db.get_leaderboard()]
    matches = [dict(r) for r in db.get_matches(limit=20)]
    bots = t.discover_bots()
    return jsonify({
        'state': state,
        'leaderboard': leaderboard,
        'recent_matches': matches,
        'bot_count': len(bots),
    })


@app.route('/api/start', methods=['POST'])
def api_start():
    global _tournament_thread
    with _tournament_lock:
        state = dict(db.get_tournament_state())
        if state['status'] == 'running':
            return jsonify({'error': 'Tournament already running'}), 400

        bots = t.discover_bots()
        if len(bots) < 2:
            return jsonify({
                'error': f'Need at least 2 bots in bots/ directory, found {len(bots)}'
            }), 400

        db.reset_tournament()

        def _run():
            t.run_tournament()

        _tournament_thread = threading.Thread(target=_run, daemon=True)
        _tournament_thread.start()

    return jsonify({'status': 'started', 'bot_count': len(bots)})


@app.route('/api/reset', methods=['POST'])
def api_reset():
    with _tournament_lock:
        state = dict(db.get_tournament_state())
        if state['status'] == 'running':
            return jsonify({'error': 'Cannot reset while tournament is running'}), 400
        db.reset_tournament()
    return jsonify({'status': 'reset'})


@app.route('/api/match/<int:match_id>/log')
def api_match_log(match_id):
    match = db.get_match(match_id)
    if not match:
        abort(404)
    match = dict(match)
    if not match.get('log_path'):
        return jsonify({'log': None})
    try:
        with open(match['log_path'] + '.txt', 'r') as f:
            return jsonify({'log': f.read()})
    except FileNotFoundError:
        return jsonify({'log': None})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    db.init_db()

    # If a previous session crashed mid-tournament, reset the status
    state = dict(db.get_tournament_state())
    if state['status'] == 'running':
        db.update_tournament_state(status='idle')

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9000

    # Find the machine's LAN IP so participants know where to submit
    try:
        import socket as _socket
        _s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        _s.connect(('8.8.8.8', 80))
        local_ip = _s.getsockname()[0]
        _s.close()
    except Exception:
        local_ip = 'localhost'

    print('┌──────────────────────────────────────────────────┐')
    print('│  HopAI Pokerbots Dashboard                        │')
    print('│                                                    │')
    print(f'│  Your machine (you):  http://localhost:{port:<12} │')
    print(f'│  Participants:        http://{local_ip}:{port:<5}         │')
    print('│                                                    │')
    print('│  Share the Participants URL with your teams.       │')
    print('│  They open it in a browser to submit their bot.   │')
    print('│  Ctrl+C to stop.                                   │')
    print('└──────────────────────────────────────────────────┘')
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
