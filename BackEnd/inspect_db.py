from pymongo import MongoClient

def run():
    client = MongoClient('mongodb://localhost:27017/')
    db = client['talend_db']
    for doc in db['cvs'].find():
        print(f"Name: {doc.get('name')}, original: {doc.get('original_filename')}, stored: {doc.get('stored_filename')}")

if __name__ == '__main__':
    run()
