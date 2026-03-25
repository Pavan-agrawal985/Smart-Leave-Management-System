let leaveTypes = JSON.parse(localStorage.getItem("leaveTypes")) || [];

displayLeaveTypes();

let form = document.getElementById("leaveTypeForm");

if (form) {
    form.addEventListener("submit", function(e) {
        e.preventDefault();

        let type = document.getElementById("leaveType").value;

        leaveTypes.push(type);

        localStorage.setItem("leaveTypes", JSON.stringify(leaveTypes));

        displayLeaveTypes();
        this.reset();
    });
}

function displayLeaveTypes() {
    let table = document.getElementById("leaveTypeTable");

    if (!table) return;

    table.innerHTML = `
        <tr>
            <th>Leave Type</th>
            <th>Action</th>
        </tr>
    `;

    leaveTypes.forEach((type, index) => {
        table.innerHTML += `
            <tr>
                <td>${type}</td>
                <td>
                    <button onclick="deleteType(${index})" class="delete">Delete</button>
                </td>
            </tr>
        `;
    });
}

function deleteType(index) {
    leaveTypes.splice(index, 1);

    localStorage.setItem("leaveTypes", JSON.stringify(leaveTypes));

    displayLeaveTypes();
}

// ✅ Leave Policy Logic
let policyForm = document.getElementById("policyForm");

if (policyForm) {
    let savedPolicy = JSON.parse(localStorage.getItem("leavePolicy"));

    if (savedPolicy) {
        document.getElementById("policyDisplay").innerText =
            `Sick: ${savedPolicy.sick}, Casual: ${savedPolicy.casual}`;
    }

    policyForm.addEventListener("submit", function(e) {
        e.preventDefault();

        let sick = document.getElementById("sick").value;
        let casual = document.getElementById("casual").value;

        let policy = { sick, casual };

        localStorage.setItem("leavePolicy", JSON.stringify(policy));

        document.getElementById("policyDisplay").innerText =
            `Sick: ${sick}, Casual: ${casual}`;

        alert("Policy Saved!");
    });
}