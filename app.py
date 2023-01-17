from flask import Flask, jsonify, request
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
load_dotenv()

app = Flask(__name__)

uri = os.getenv('URI')
user = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "test1234"), database="neo4j")


@app.route("/employees", methods=["GET"])
def get_employees():
    with driver.session() as session:
        result = session.run(
            "MATCH (e:Employee) RETURN e.first_name as first_name, e.last_name as last_name, e.age as age, e.role as role ORDER BY e.first_name")
        employees = []
        for record in result:
            employee = {
                "first_name": record["first_name"],
                "last_name": record["last_name"],
                "age": record["age"],
                "role": record["role"]
            }
            employees.append(employee)
    return jsonify(employees)


def check_unique_name(first_name, last_name):
    query = f"MATCH (e:Employee) WHERE e.first_name = '{first_name}' AND e.last_name = '{last_name}' RETURN e"
    with driver.session() as session:
        result = session.run(query)
        if result.peek():
            return True
    return False


@app.route("/employees", methods=["POST"])
def add_employee():
    data = request.get_json()
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    age = data.get("age")
    role = data.get("role")
    department = data.get("department")

    if not all([first_name, last_name, age, role, department]):
        return jsonify({"message": "All fields are required"}), 400
    if check_unique_name(first_name, last_name):
        return jsonify({"message": "Employee with this name already exists"}), 400

    query = f"CREATE (e:Employee {{first_name: '{first_name}', last_name: '{last_name}', age: {age}, role: '{role}'}})"
    query += f"CREATE (d:Department {{name: '{department}'}})"
    query += f"CREATE (e)-[:WORKS_IN]->(d)"
    with driver.session() as session:
        session.run(query)
    return jsonify({"message": "Employee added successfully"})


@app.route("/employees/<int:id>", methods=["PUT"])
def update_employee(id):
    data = request.get_json()
    first_name = data.get("first_name")
    last_name = data.get("last_name")
    role = data.get("role")
    department = data.get("department")

    if not any([first_name, last_name, role, department]):
        return jsonify({"message": "At least one field must be provided"}), 400

    query = f"MATCH (e:Employee) WHERE id(e) = {id} SET "
    if first_name:
        query += f"e.first_name = '{first_name}', "
    if last_name:
        query += f"e.last_name = '{last_name}', "
    if role:
        query += f"e.role = '{role}', "
    if department:
        query += f"e.department = '{department}', "
    query = query[:-2]
    query += "RETURN e.first_name as first_name, e.last_name as last_name, e.role as role, e.department as department"
    with driver.session() as session:
        result = session.run(query)
        if result.peek():
            employee = result.single()
            return jsonify({
                "first_name": employee["first_name"],
                "last_name": employee["last_name"],
                "role": employee["role"],
                "department": employee["department"]
            })
    return jsonify({"message": "Employee not found"}), 404


@app.route("/employees/<int:id>", methods=["DELETE"])
def delete_employee(id):
    query = f"MATCH (e:Employee) WHERE id(e) = {id} "
    query += f"OPTIONAL MATCH (d:Department)<-[:MANAGES]-(e) "
    query += "WITH e,d "
    query += "WHERE e IS NOT NULL "
    query += "DETACH DELETE e "
    query += "WITH d "
    query += "WHERE d IS NOT NULL "
    query += "SET d.manager = null "
    query += "WITH d "
    query += "WHERE NOT (d)<-[:MANAGES]-() "
    query += "DETACH DELETE d"
    with driver.session() as session:
        session.run(query)
    return jsonify({"message": "Employee deleted successfully"})


@app.route("/employees/<int:id>/subordinates", methods=["GET"])
def get_subordinates(id):
    query = f"MATCH (e:Employee)-[:MANAGES]->(:Department)<-[:WORKS_IN]-(s:Employee) WHERE id(e) = {id} "
    query += "RETURN s.first_name as first_name, s.last_name as last_name, s.age as age, s.role as role"
    with driver.session() as session:
        result = session.run(query)
        subordinates = []
        for record in result:
            subordinate = {
                "first_name": record["first_name"],
                "last_name": record["last_name"],
                "age": record["age"],
                "role": record["role"]
            }
            subordinates.append(subordinate)
    return jsonify(subordinates)


@app.route("/employees/<employee_id>/department", methods=["GET"])
def get_employee_department(employee_id):
    query = f"MATCH (e:Employee)-[:WORKS_IN]->(d:Department) WHERE e.id = {employee_id} MATCH (d)-[:WORKS_IN]->(e:Employee) RETURN d.name as department_name, COUNT(e) as number_of_employees, d.manager as manager"
    with driver.session() as session:
        result = session.run(query)
        departments = []
        for record in result:
            department = {
                "department_name": record["department_name"],
                "number_of_employees": record["number_of_employees"],
                "manager": record["manager"]
            }
            departments.append(department)
    return jsonify(departments)


@app.route("/departments", methods=["GET"])
def get_departments():
    name = request.args.get("name")
    sort_by = request.args.get("sort_by")

    query = "MATCH (d:Department)"
    if name and sort_by:
        query += f" WHERE d.name CONTAINS '{name}' WITH d ORDER BY d.{sort_by}"
    elif name:
        query += f" WHERE d.name CONTAINS '{name}'"
    elif sort_by:
        query += f" WITH d ORDER BY d.{sort_by} "
    query += " RETURN d.name as name, COUNT(d) as number_of_employees"
    with driver.session() as session:
        result = session.run(query)
        departments = []
        for record in result:
            department = {
                "name": record["name"],
                "number_of_employees": record["number_of_employees"]
            }
            departments.append(department)
    return jsonify(departments)


@app.route("/departments/<department_id>/employees", methods=["GET"])
def get_employees_by_department(department_id):
    query = f"MATCH (e:Employee)-[:WORKS_IN]->(d:Department) WHERE d.id = {int(department_id)} RETURN e.first_name as first_name, e.last_name as last_name, e.age as age, e.role as role"
    with driver.session() as session:
        result = session.run(query)
        employees = []
        for record in result:
            employee = {
                "first_name": record["first_name"],
                "last_name": record["last_name"],
                "age": record["age"],
                "role": record["role"]
            }
            employees.append(employee)
    return jsonify(employees)


if __name__ == '__main__':
    app.run()
