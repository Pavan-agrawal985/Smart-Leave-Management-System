const form = document.getElementById("userForm");
const table = document.querySelector("table");

form.addEventListener("submit", function(e) {
    e.preventDefault();

    let name = form.querySelector("input[type='text']").value;
    let email = form.querySelector("input[type='email']").value;
    let role = form.querySelector("select").value;

    let row = table.insertRow();

    row.innerHTML = `
        <td>${name}</td>
        <td>${email}</td>
        <td>${role}</td>
        <td>Active</td>
        <td>
            <button onclick="toggleStatus(this)">Deactivate</button>
            <button style="background:red;" onclick="deleteRow(this)">Delete</button>
        </td>
    `;

    form.reset();
});

function deleteRow(btn) {
    btn.parentElement.parentElement.remove();
}

function toggleStatus(btn) {
    let row = btn.parentElement.parentElement;
    let status = row.cells[3];

    if (status.innerText === "Active") {
        status.innerText = "Inactive";
        btn.innerText = "Activate";
    } else {
        status.innerText = "Active";
        btn.innerText = "Deactivate";
    }
}