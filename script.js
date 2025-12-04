const form = document.getElementById("farmerForm");
const cardPlaceholder = document.getElementById("cardPlaceholder");

function maskAadhaar(aadhaar) {
    if (aadhaar.length < 4) return "XXXX XXXX XXXX";
    const last4 = aadhaar.slice(-4);
    return "XXXX XXXX " + last4;
}

function generateEFN(district) {
    const prefix = "EFN";
    const districtCode = (district || "IND").toUpperCase().slice(0, 3);
    const randomPart = Math.floor(100000 + Math.random() * 900000); // 6-digit
    return `${prefix}-${districtCode}-${randomPart}`;
}

form.addEventListener("submit", (event) => {
    event.preventDefault();

    const name = document.getElementById("farmerName").value.trim();
    const aadhaar = document.getElementById("aadhaar").value.trim();
    const rationCard = document.getElementById("rationCard").value.trim();
    const phone = document.getElementById("phone").value.trim();
    const village = document.getElementById("village").value.trim();
    const district = document.getElementById("district").value.trim();
    const landArea = document.getElementById("landArea").value.trim();

    const maskedAadhaar = maskAadhaar(aadhaar);
    const efn = generateEFN(district);

    cardPlaceholder.classList.remove("empty");
    cardPlaceholder.innerHTML = `
        <div class="card-header">
            <div class="card-title">${name || "Farmer Name"}</div>
            <div class="efn-tag">${efn}</div>
        </div>
        <div class="card-row">
            <span class="card-label">Aadhaar</span>
            <span class="card-value">${maskedAadhaar}</span>
        </div>
        <div class="card-row">
            <span class="card-label">Ration Card</span>
            <span class="card-value">${rationCard || "-"}</span>
        </div>
        <div class="card-row">
            <span class="card-label">Phone</span>
            <span class="card-value">${phone || "-"}</span>
        </div>
        <div class="card-row">
            <span class="card-label">Location</span>
            <span class="card-value">${village || "-"}, ${district || "-"}</span>
        </div>
        <div class="card-row">
            <span class="card-label">Land Area</span>
            <span class="card-value">${landArea || "0"} acres</span>
        </div>
        <div class="card-row">
            <span class="card-label">Status</span>
            <span class="card-value">Identity linked · Entitlement pending</span>
        </div>
    `;

    // For now, just log in console (later we will store it properly)
    console.log("Registered Farmer:", {
        efn,
        name,
        aadhaar,
        rationCard,
        phone,
        village,
        district,
        landArea
    });
});
