document.addEventListener("DOMContentLoaded", async () => {
    const requete = await fetch("http://127.0.0.1:8000/api/liste-cameras");
    if (!requete.ok) {
        console.error("Erreur récupération caméras");
        return;
    }

    const reponse = await requete.json();
    console.log(reponse )
    const container = document.getElementById("divListeCameras");
    container.innerHTML = "";


    reponse.ip.forEach((ipCamera, index) => {
        const camera = document.createElement("div");
        camera.className = "camera";
        camera.dataset.ip = ipCamera;

        camera.innerHTML = `
            <div class="loader"></div>
            <img class="video" style="display:none;">
        `;

        camera.addEventListener("click", () => {
            window.location.href = `camera.html?ip=${ipCamera}`;
        });

        container.appendChild(camera);

        const ws = new WebSocket(`ws://localhost:8000/ws/camera?ip=${ipCamera}`);
        ws.onmessage = (event) => {
            const img = camera.querySelector("img");
            const loader = camera.querySelector(".loader");

            img.src = `data:image/jpeg;base64,${event.data}`;
            img.style.display = "block";
            loader.style.display = "none";
        };
    });

    const requeteListeCameras = await fetch("http://127.0.0.1:8000/api/liste-cameras");
    if (!requeteListeCameras.ok) {
        console.error("Erreur récupération caméras");
        return;
    }
    const reponseListeCameras = await requeteListeCameras.json();
    let navHtml = `
    <li><a href="./">Accueil</a></li>
    <li><a href="./liste-visages.html">Liste des visages</a></li>
    `;

    reponseListeCameras.ip.forEach((ip, i) => {
        navHtml += `<li><a href="./camera.html?ip=${ip}">Caméra ${i + 1}</a></li>`;
    });

    document.querySelector(".navbar ul").innerHTML = navHtml;

})
