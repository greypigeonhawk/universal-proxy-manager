import sqlite3,datetime
from typing import Dict,Optional,Any

class AppLauncherDB:
    
    def __init__(self, db_path="data/app_launcher.db"):
        self.db_path = db_path
    
    def create_tables(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS apps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            path TEXT NOT NULL UNIQUE,
            launch_count INTEGER DEFAULT 0,
            last_launch_time TEXT,
            icon BLOB
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        ''')
        conn.commit()
        conn.close()
    
    def add_app(self, name, path, icon_data=None):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO apps (name, path, icon) VALUES (?, ?, ?)",
                (name, path, icon_data)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def update_launch_stats(self, app_id):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE apps SET launch_count = launch_count + 1, last_launch_time = ? WHERE id = ?",
            (now, app_id)
        )
        conn.commit()
        conn.close()

    def update_app_icon(self, app_id, icon_data):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE apps SET icon = ? WHERE id = ?",
            (icon_data, app_id)
        )
        conn.commit()
        conn.close()

    def save_latest_app(self, app_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "REPLACE INTO app_config (key, value) VALUES ('latest_app', ?)",
            (str(app_id),)
        )
        conn.commit()
        conn.close()
    
    def get_latest_app_id(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_config WHERE key = 'latest_app'")
        result = cursor.fetchone()
        conn.close()
        return int(result[0]) if result else None
    
    def delete_app(self, app_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM apps WHERE id = ?", (app_id,))
        conn.commit()
        conn.close()
    
    def get_all_apps(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM apps ORDER BY last_launch_time DESC, launch_count DESC")
        apps = cursor.fetchall()
        conn.close()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in apps]

class ToolConfigDB:
    
    def __init__(self, db_path: str = "data/tools.db"):
        self.db_path = db_path

    def save_tool(self, tool_data: Dict[str, Any]) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            tool_id = tool_data.get('id')
            if tool_id:
                cursor.execute('SELECT id FROM tools WHERE id = ?', (tool_id,))
                exists = cursor.fetchone() is not None
            if tool_id and exists:
                cursor.execute('''
                    UPDATE tools SET
                        name = ?,
                        path = ?,
                        urls = ?,
                        agency = ?,
                        port = ?,
                        para1 = ?,
                        para2 = ?,
                        para3 = ?,
                        launch_times = ?,
                        latest_launch_time = ?
                    WHERE id = ?
                ''', (
                    tool_data['name'],
                    tool_data['path'],
                    ','.join(tool_data['url']) if tool_data['url'] else '',
                    tool_data['agency'],
                    tool_data['port'],
                    tool_data['para1'],
                    tool_data['para2'],
                    tool_data['para3'],
                    tool_data['launch_times'],
                    tool_data['latest_launch_time'],
                    tool_id
                ))
                result_id = tool_id
            else:
                cursor.execute('''
                    INSERT INTO tools (
                        name, path, urls, agency, port, para1, para2, para3, launch_times, latest_launch_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    tool_data['name'],
                    tool_data['path'],
                    ','.join(tool_data['url']) if tool_data['url'] else '',
                    tool_data['agency'],
                    tool_data['port'],
                    tool_data['para1'],
                    tool_data['para2'],
                    tool_data['para3'],
                    tool_data['launch_times'],
                    tool_data['latest_launch_time']
                ))
                result_id = cursor.lastrowid
            conn.commit()
            return result_id

    def load_tool(self, tool_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tools WHERE id = ?", (tool_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_dict(row)

    def load_all_tools(self) -> Dict[str, Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tools")
            rows = cursor.fetchall()
            return {row[0]: self._row_to_dict(row) for row in rows}

    def _row_to_dict(self, row) -> Dict[str, Any]:
        urls = row[3].split(',') if row[3] else []
        return {
            'id': row[0],
            'name': row[1],
            'path': row[2],
            'url': urls,
            'agency': row[4],
            'port': row[5],
            'para1': row[6],
            'para2': row[7],
            'para3': row[8],
            'launch_times': row[9],
            'latest_launch_time': row[10]
        }

    def delete_tool(self, tool_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tools WHERE id = ?", (tool_id,))
            conn.commit()

    def initialize_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tools (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    path TEXT,
                    urls TEXT,
                    agency TEXT,
                    port INTEGER,
                    para1 TEXT,
                    para2 TEXT,
                    para3 TEXT,
                    launch_times INTEGER,  
                    latest_launch_time TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tool_config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            conn.commit()

    def update_launch(self, tool_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT launch_times FROM tools WHERE id = ?", (tool_id,))
            result = cursor.fetchone()
            if result:
                current_times = result[0] if result[0] is not None else 0
                new_times = current_times + 1
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "UPDATE tools SET launch_times = ?, latest_launch_time = ? WHERE id = ?",
                    (new_times, current_time, tool_id)
                )
                conn.commit()
            else:
                raise ValueError(f"Tool ID '{tool_id}' does not exist")

    def save_latest_tool(self, tool_id: int) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO tool_config (key, value) VALUES (?, ?)",
                ("latest_tool_id", str(tool_id))
            )
            conn.commit()

    def get_latest_toolid(self) -> Optional[int]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM tool_config WHERE key = 'latest_tool_id'")
            result = cursor.fetchone()
            return int(result[0]) if (result and result[0].isdigit()) else None

class NetConnDB:
    
    def __init__(self, fav_db: str = "data/fav_conn.db", history_db: str = "data/history_download.db"):
        self.fav_db = fav_db
        self.history_db = history_db

    def initialize_fav_db(self) -> None:
        with sqlite3.connect(self.fav_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    url TEXT,
                    last_launch_time TEXT,
                    launch_times INTEGER
                )
            ''')
            conn.commit()

    def add_favorite(self, name: str, url: str) -> int:
        with sqlite3.connect(self.fav_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO favorites (name, url, last_launch_time, launch_times)
                VALUES (?, ?, ?, ?)
            ''', (name, url, '', 0))
            conn.commit()
            return cursor.lastrowid

    def remove_favorite(self, fav_id: int) -> None:
        with sqlite3.connect(self.fav_db) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM favorites WHERE id = ?", (fav_id,))
            conn.commit()

    def get_all_favorites(self) -> Dict[int, Dict[str, Any]]:
        with sqlite3.connect(self.fav_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM favorites")
            rows = cursor.fetchall()
            return {
                row[0]: {
                    'id': row[0],
                    'name': row[1],
                    'url': row[2],
                    'last_launch_time': row[3],
                    'launch_times': row[4]
                } for row in rows
            }

    def update_fav_launch(self, fav_id: int) -> None:
        with sqlite3.connect(self.fav_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT launch_times FROM favorites WHERE id = ?", (fav_id,))
            row = cursor.fetchone()
            if row:
                new_times = (row[0] or 0) + 1
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute(
                    "UPDATE favorites SET last_launch_time = ?, launch_times = ? WHERE id = ?",
                    (now, new_times, fav_id)
                )
                conn.commit()

    def initialize_download_db(self) -> None:
        with sqlite3.connect(self.history_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    url TEXT,
                    file_path TEXT,
                    download_time TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    url TEXT,
                    visit_time TEXT
                )
            ''')
            conn.commit()

    def add_download(self, name: str, url: str, file_path: str) -> int:
        with sqlite3.connect(self.history_db) as conn:
            cursor = conn.cursor()
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('''
                INSERT INTO downloads (name, url, file_path, download_time)
                VALUES (?, ?, ?, ?)
            ''', (name, url, file_path, now))
            conn.commit()
            return cursor.lastrowid

    def get_all_downloads(self) -> Dict[int, Dict[str, Any]]:
        with sqlite3.connect(self.history_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM downloads")
            rows = cursor.fetchall()
            return {
                row[0]: {
                    'id': row[0],
                    'name': row[1],
                    'url': row[2],
                    'file_path': row[3],
                    'download_time': row[4]
                } for row in rows
            }

    def add_history(self, name: str, url: str) -> int:
        with sqlite3.connect(self.history_db) as conn:
            cursor = conn.cursor()
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('''
                INSERT INTO history (name, url, visit_time)
                VALUES (?, ?, ?)
            ''', (name, url, now))
            conn.commit()
            return cursor.lastrowid

    def get_all_history(self) -> Dict[int, Dict[str, Any]]:
        with sqlite3.connect(self.history_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM history")
            rows = cursor.fetchall()
            return {
                row[0]: {
                    'id': row[0],
                    'name': row[1],
                    'url': row[2],
                    'visit_time': row[3]
                } for row in rows
            }

