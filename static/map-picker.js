document.addEventListener("DOMContentLoaded", function () {
    var mapEl = document.getElementById("map");
    if (!mapEl) return;

    var latInput = document.getElementById("latitude");
    var lngInput = document.getElementById("longitude");
    var locationInput = document.getElementById("location");
    var hint = document.getElementById("mapHint");
    var locateBtn = document.getElementById("locateBtn");

    var defaultCenter = [9.7872, 125.4950]; // Surigao City - change to your area
    var startLat = parseFloat(latInput.value);
    var startLng = parseFloat(lngInput.value);
    var hasPin = !isNaN(startLat) && !isNaN(startLng);

    var map = L.map("map").setView(hasPin ? [startLat, startLng] : defaultCenter, hasPin ? 16 : 13);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors"
    }).addTo(map);

    var marker = null;

    function fillLocationName(lat, lng) {
        if (locationInput.value.trim() !== "") return; // don't overwrite what they typed
        fetch("https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=" + lat + "&lon=" + lng)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var a = data.address || {};
                var parts = [
                    a.neighbourhood || a.suburb || a.village || a.quarter,
                    a.city || a.town || a.municipality
                ].filter(Boolean);
                if (parts.length && locationInput.value.trim() === "") {
                    locationInput.value = parts.join(", ");
                }
            })
            .catch(function () { /* ignore - user can type it */ });
    }

    function setPin(lat, lng, fillName) {
        latInput.value = lat.toFixed(6);
        lngInput.value = lng.toFixed(6);
        if (marker) {
            marker.setLatLng([lat, lng]);
        } else {
            marker = L.marker([lat, lng], { draggable: true }).addTo(map);
            marker.on("dragend", function () {
                var p = marker.getLatLng();
                setPin(p.lat, p.lng, false);
            });
        }
        hint.textContent = "Pin set at " + lat.toFixed(5) + ", " + lng.toFixed(5) + " (drag to adjust)";
        if (fillName) fillLocationName(lat, lng);
    }

    if (hasPin) setPin(startLat, startLng, false);

    map.on("click", function (e) {
        setPin(e.latlng.lat, e.latlng.lng, true);
    });

    locateBtn.addEventListener("click", function () {
        if (!navigator.geolocation) {
            hint.textContent = "Your browser doesn't support GPS.";
            return;
        }
        hint.textContent = "Finding your location...";
        navigator.geolocation.getCurrentPosition(
            function (pos) {
                setPin(pos.coords.latitude, pos.coords.longitude, true);
                map.setView([pos.coords.latitude, pos.coords.longitude], 17);
            },
            function () {
                hint.textContent = "Couldn't get your location. Allow location access or tap the map instead.";
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    });
});