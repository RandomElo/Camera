document.addEventListener("DOMContentLoaded", async () => {
    const tbody = document.querySelector("tbody");
    const modal = document.getElementById("editModal");
    const input = document.getElementById("editInput");
    const btnSave = document.getElementById("saveEdit");
    const btnClose = document.getElementById("closeEdit");
    const modalTitle = document.querySelector(".modal-content h2");

    let currentId = null;
    let currentRow = null;
    function showToast(msg) {
        alert(msg);
    }

    function openEditModal(id, nom, row) {
        currentId = id;
        currentRow = row;
        input.value = nom || "";
        modalTitle.textContent = "Modifier le nom";
        modal.style.display = "flex";
        input.focus();
    }

    function closeModal() {
        modal.style.display = "none";
        currentId = null;
        currentRow = null;
    }

    modal.addEventListener("click", (e) => {
        if (e.target === modal) closeModal();
    });
    btnClose.addEventListener("click", closeModal);

    try {
        const req = await fetch("http://localhost:8000/api/visages-enregistrer");
        if (!req.ok) throw new Error("Erreur lors de la récupération des visages");
        const visages = await req.json();

        let html = "";
        for (const visage of visages) {
            const safeName = String(visage.name || "").replace(/</g, "&lt;").replace(/>/g, "&gt;");
            const imgSrc = visage.image ? `data:image/jpeg;base64,${visage.image}` : "https://via.placeholder.com/80";

            html += `
            <tr data-id="${visage.id}">
                <td class="tdName">${safeName}</td>
                <td class="tdVisage">
                    <img src="${imgSrc}" alt="Visage ${safeName}" />
                </td>
                <td>
                    <img src="./img/crayon.png" class="imgCrayon" data-id="${visage.id}" data-nom="${safeName}" alt="Modifier" style="cursor:pointer" />
                </td>
            </tr>`;
        }
        tbody.innerHTML = html;

        document.querySelectorAll(".imgCrayon").forEach((icone) => {
            icone.addEventListener("click", (e) => {
                const id = icone.dataset.id;
                const nom = icone.dataset.nom || "";
                const row = icone.closest("tr");
                openEditModal(id, nom, row);
            });
        });

    } catch (err) {
        console.error(err);
        showToast("Impossible de charger la liste des visages.");
    }

    btnSave.addEventListener("click", async () => {
        const nouveauNom = input.value.trim();
        if (!nouveauNom) {
            showToast("Le nom ne peut pas être vide.");
            return;
        }
        if (!currentId) {
            showToast("Erreur interne : id manquant.");
            return;
        }

        try {
            const res = await fetch("http://localhost:8000/api/modifier-nom", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ id: currentId, nom: nouveauNom })
            });

            if (res.status === 422) {
                let errText = "Données invalides (422).";
                try {
                    const j = await res.json();
                    if (j.detail) errText = j.detail;
                    else if (j.message) errText = j.message;
                } catch (_) {}
                showToast("Erreur : " + errText);
                return;
            }

            if (!res.ok) {
                showToast("Erreur serveur lors de la modification.");
                return;
            }

            if (currentRow) {
                const tdName = currentRow.querySelector(".tdName");
                const crayon = currentRow.querySelector(".imgCrayon");
                if (tdName) tdName.textContent = nouveauNom;
                if (crayon) crayon.dataset.nom = nouveauNom;
            }

            closeModal();
            showToast("Nom modifié !");
        } catch (err) {
            console.error(err);
            showToast("Erreur réseau lors de la modification.");
        }
    });

    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") btnSave.click();
        if (e.key === "Escape") closeModal();
    });

    try {
        const reqCams = await fetch("http://127.0.0.1:8000/api/liste-cameras");
        if (reqCams.ok) {
            const rep = await reqCams.json();
            let navHtml = `
                <li><a href="./">Accueil</a></li>
                <li><a href="./liste-visages.html">Liste des visages</a></li>
            `;
            rep.ip.forEach((ip, i) => {
                navHtml += `<li><a href="./camera.html?ip=${ip}">Caméra ${i + 1}</a></li>`;
            });
            document.querySelector(".navbar ul").innerHTML = navHtml;
        }
    } catch (err) {
        console.warn("Impossible de charger la liste des caméras pour la navbar");
    }
});
