let facultyList = JSON.parse(localStorage.getItem("facultyList")) || [];

displayFaculty();

document.getElementById("facultyForm").addEventListener("submit", function(e) {
    e.preventDefault();

    let name = document.getElementById("name").value;
    let email = document.getElementById("email").value;
    let department = document.getElementById("department").value;

    let faculty = { name, email, department };
    facultyList.push(faculty);

    // SAVE DATA
    localStorage.setItem("facultyList", JSON.stringify(facultyList));

    displayFaculty();
    this.reset();
});

function displayFaculty() {
    let table = document.getElementById("facultyTable");

    table.innerHTML = `
        <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Department</th>
            <th>Action</th>
        </tr>
    `;

    facultyList.forEach((f, index) => {
        table.innerHTML += `
            <tr>
                <td>${f.name}</td>
                <td>${f.email}</td>
                <td>${f.department}</td>
                <td>
                    <button onclick="deleteFaculty(${index})" style="background:red;color:white;">Delete</button>
                </td>
            </tr>
        `;
    });
}

function deleteFaculty(index) {
    facultyList.splice(index, 1);

    // UPDATE STORAGE
    localStorage.setItem("facultyList", JSON.stringify(facultyList));

    displayFaculty();
}