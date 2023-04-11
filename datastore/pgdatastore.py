import os 
import hashlib
import shutil
from datetime import datetime
import psycopg2
import uuid  

db_name = 'aidb'
db_user = 'dbroot'
db_password = '2RscyI6I'
db_host = '8.134.70.20'

file_type = os.environ.get("MILVUS_COLLECTION")
    
def get_db_conn():
    conn = psycopg2.connect(database=db_name, user=db_user, password=db_password, 
                            host=db_host, port="5432")
    return conn

def get_file_md5(filename):
    md5 = hashlib.md5()
    with open(filename, 'rb') as f:
        while True:
            data = f.read(1024 * 1024)  # 读取文件内容
            if not data:
                break
            md5.update(data)  # 更新MD5值
    return md5.hexdigest()

def get_info_md5(info):
    md5 = hashlib.md5()
    md5.update(info.encode('utf-8'))
    return md5.hexdigest()

def insert_data_to_pg(file, md5, size, modelname) -> str:
    conn = get_db_conn()
    cursor = conn.cursor()

    cursor.execute("""SELECT embedding_status FROM public.tb_gpt_embedding_files 
            WHERE file_md5 = '{}' and embedding_status = 0 and file_type = '{}'""".format(md5, file_type))
    rows = cursor.fetchall() 
    if len(rows) > 0:
        print(rows[0])
        return  
    
    try:
        sql = '''
        INSERT INTO public.tb_gpt_embedding_files(local_file, file_name, file_md5, file_size, embedding_resp, 
            embedding_status,push_time, file_type, model_name) 
        VALUES ('{}', '{}', '{}', {}, '', 0, now(), '{}', '{}')
        '''.format(file, os.path.basename(file), md5, size, file_type, modelname)
        cursor.execute(sql)
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error insert_data_to_pg {e.pgcode}: {e.pgerror}, {sql}")
        cursor.close()
        conn.close()
        return e.pgerror
    cursor.close()
    conn.close()
    return 'ok'

def update_file_embedding_result(file_md5, result):
    conn = get_db_conn()
    cursor = conn.cursor()
    try: 
        cursor.execute("""UPDATE public.tb_gpt_embedding_files SET embedding_resp = '{}', 
            embedding_status = 1, update_time = now() WHERE file_md5 = '{}' and embedding_status = 0 
            and file_type='{}'""".format(result[0].query, file_md5, file_type))
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error update_file_embedding_result, {e.pgcode}: {e.pgerror}")
        cursor.close()
        conn.close()
        return e.pgerror  
    cursor.close()
    conn.close()
    print('update embedding result successfully!', "file_md5:", file_md5, "result:", result)

#获取是否已经embedding
def get_file_is_embedding(file_md5) -> bool: 
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("""SELECT embedding_status FROM public.tb_gpt_embedding_files 
        WHERE file_md5 = '{}' and embedding_status != 0 and file_type='{}'""".format(file_md5, file_type))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return len(rows) > 0


def add_gpt_chat_log(user_name, message_type, gpt_model, message_data)->str:
    conn = get_db_conn()
    cursor = conn.cursor()
    log_id = uuid.uuid4() 
    try:
        sql = '''
        INSERT INTO public.tb_gpt_chat_logs(log_id, user_name, message_type, 
            gpt_model, message_data, push_time) 
        VALUES ('{}','{}', '{}', '{}', '{}', now())
        '''.format(log_id, user_name, message_type, gpt_model, message_data.replace("'", "''"))
        cursor.execute(sql)
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error add_gpt_chat_log {e.pgcode}: {e.pgerror}, {sql}")
        cursor.close()
        conn.close()
        return ''
    cursor.close()
    conn.close()
    return log_id


def update_gpt_chat_log_embedding(log_id, embedding_data)->str: 
     
    data_str = ''
    for r in embedding_data:
        # 第一层 QueryResult 对象 
        for rr in r.results:     
            # 第二层 DocumentChunkWithScore 对象
            data_str = "{},{}-{}".format(data_str, rr.id, rr.text)

    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        sql = '''
        UPDATE public.tb_gpt_chat_logs SET embedding_data = '{}', embedding_time = now() 
        WHERE log_id = '{}'
        '''.format(data_str.replace("'", "''"), log_id)
        cursor.execute(sql)
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error update_gpt_chat_log_embedding {e.pgcode}: {e.pgerror}, {sql}")
        cursor.close()
        conn.close()
        return ''
    cursor.close()
    conn.close()
    return log_id


def update_gpt_chat_log_response(log_id, prompt_data, result_data)->str:
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        sql = '''
        UPDATE public.tb_gpt_chat_logs SET prompt_data = '{}', result_data='{}', result_time = now() 
        WHERE log_id = '{}'
        '''.format(prompt_data.replace("'", "''"), result_data.replace("'", "''"), log_id)
        cursor.execute(sql)
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error update_gpt_chat_log_response {e.pgcode}: {e.pgerror}, {sql}")
        cursor.close()
        conn.close()
        return ''
    cursor.close()
    conn.close()
    return log_id