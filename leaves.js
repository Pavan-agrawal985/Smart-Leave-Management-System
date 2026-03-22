document.querySelectorAll(".approve").forEach(btn => {
    btn.addEventListener("click", function () {
        let row = this.closest("tr");
        row.cells[5].innerText = "Approved";
    });
});

document.querySelectorAll(".reject").forEach(btn => {
    btn.addEventListener("click", function () {
        let row = this.closest("tr");
        row.cells[5].innerText = "Rejected";
    });
});