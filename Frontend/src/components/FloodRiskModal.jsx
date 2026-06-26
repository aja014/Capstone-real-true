import { useEffect, useRef } from "react";
import { X } from "lucide-react";

const LOCATION = {
  lat: 14.8138,
  lng: 121.0448,
  zoom: 16,
};

function LeafletMap() {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);

  useEffect(() => {
    const initMap = () => {
      if (!mapRef.current || mapInstanceRef.current) return;
      const L = window.L;
      if (!L) return;

      mapInstanceRef.current = L.map(mapRef.current, {
        center: [LOCATION.lat, LOCATION.lng],
        zoom: LOCATION.zoom,
        zoomControl: true,
        scrollWheelZoom: false,
        attributionControl: false,
      });

      L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 19 }
      ).addTo(mapInstanceRef.current);

      const redIcon = L.divIcon({
        className: "",
        html: `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="36" viewBox="0 0 28 36">
          <path d="M14 0C6.27 0 0 6.27 0 14c0 9.33 14 22 14 22s14-12.67 14-22C28 6.27 21.73 0 14 0z" fill="#e53e3e"/>
          <circle cx="14" cy="14" r="6" fill="white"/>
        </svg>`,
        iconSize: [28, 36],
        iconAnchor: [14, 36],
      });

      L.marker([LOCATION.lat, LOCATION.lng], { icon: redIcon }).addTo(mapInstanceRef.current);
    };

    const loadLeaflet = () => {
      if (window.L) { initMap(); return; }

      if (!document.getElementById("leaflet-css")) {
        const link = document.createElement("link");
        link.id = "leaflet-css";
        link.rel = "stylesheet";
        link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
        document.head.appendChild(link);
      }

      if (!document.getElementById("leaflet-js")) {
        const script = document.createElement("script");
        script.id = "leaflet-js";
        script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
        script.onload = initMap;
        document.head.appendChild(script);
      } else {
        // script already added, wait for it
        const poll = setInterval(() => {
          if (window.L) { clearInterval(poll); initMap(); }
        }, 100);
      }
    };

    const timer = setTimeout(loadLeaflet, 80);

    return () => {
      clearTimeout(timer);
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  return <div ref={mapRef} className="h-full w-full" />;
}

export default function FloodRiskModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-[1px]"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="relative w-[750px] rounded-2xl bg-[#F5E7B8] shadow-[0_15px_40px_rgba(0,0,0,0.18)]">

        {/* Close Button */}
        <button onClick={onClose} className="absolute right-5 top-4 z-10 text-black hover:opacity-70">
          <X size={26} strokeWidth={2.2} />
        </button>

        <div className="flex p-7">

          {/* LEFT — Live Map */}
          <div className="w-[320px] flex-shrink-0 overflow-hidden rounded-xl" style={{ height: 350 }}>
            <LeafletMap />
          </div>

          {/* DIVIDER */}
          <div className="mx-6 w-px bg-[#6D604D]" />

          {/* RIGHT CONTENT */}
          <div className="w-full flex flex-col pt-6">

            {/* LOCATION */}
            <h2 className="max-w-[210px] text-lg font-bold leading-[1.15] text-black">
              Barangay San Nicolas,<br />
              City of San Jose del Monte,<br />
              Bulacan
            </h2>

            <div className="mt-10">

              {/* SECTION TITLE */}
              <div className="mb-3 flex items-center">
                <span className="bg-[#F5E7B8] pr-2 text-sm text-black">
                  Flood Risk Assessment
                </span>
                <div className="h-px flex-1 bg-[#8A7B64]" />
              </div>

              {/* MAIN RESULT */}
              <h1 className="text-3xl font-black leading-none text-black">
                Flood Prone Area
              </h1>

              <div className="mt-2 text-md text-[#444]">
                Level: Low
              </div>

              {/* FINDINGS */}
              <ul className="mt-2 space-y-1 text-sm text-red-500">
                <li>- Low Lying Area</li>
                <li>- Clogged Drain</li>
              </ul>

            </div>
          </div>
        </div>
      </div>
    </div>
  );
}