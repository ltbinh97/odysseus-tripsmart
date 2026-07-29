import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

interface MapStop {
  id: string;
  lat: number;
  lng: number;
}

interface Props {
  stops: MapStop[];
  /** route polyline as [lat, lng] pairs (from OpenRouteService or fallback) */
  route: [number, number][];
  center: { lat: number; lng: number };
  activeId?: string | null;
  onSelect?: (id: string) => void;
}

export function ItineraryMap({ stops, route, center, activeId, onSelect }: Props) {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const fitKeyRef = useRef<string>("");

  // init once
  useEffect(() => {
    if (!elRef.current || mapRef.current) return;
    const map = L.map(elRef.current, {
      zoomControl: false,
      attributionControl: true,
      scrollWheelZoom: true,
    });
    // A view MUST be set before Leaflet will request any tiles.
    map.setView([center.lat, center.lng], 12);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      subdomains: "abcd",
      maxZoom: 20,
      attribution: "&copy; OpenStreetMap &copy; CARTO",
    }).addTo(map);
    L.control.zoom({ position: "topright" }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    // The container may still be laying out; recompute size shortly after mount.
    const t = setTimeout(() => map.invalidateSize(), 200);
    return () => {
      clearTimeout(t);
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // redraw markers + route
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    const raf = requestAnimationFrame(() => {
      map.invalidateSize();
      layer.clearLayers();

      if (route.length > 1) {
        L.polyline(route, {
          color: "#1e7a82",
          weight: 4,
          opacity: 0.85,
          lineJoin: "round",
        }).addTo(layer);
      }

      stops.forEach((s, i) => {
        const active = s.id === activeId;
        const icon = L.divIcon({
          className: "mapin-wrap",
          html: `<div class="mapin ${active ? "mapin--active" : ""}">${i + 1}</div>`,
          iconSize: [30, 30],
          iconAnchor: [15, 15],
        });
        const m = L.marker([s.lat, s.lng], { icon, zIndexOffset: active ? 1000 : 0 }).addTo(layer);
        if (onSelect) m.on("click", () => onSelect(s.id));
      });

      // Fit only when the set of stops changes (not on selection).
      const key = stops.map((s) => s.id).join("|");
      if (key !== fitKeyRef.current && stops.length) {
        fitKeyRef.current = key;
        const bounds = L.latLngBounds(stops.map((s) => [s.lat, s.lng] as [number, number]));
        if (bounds.isValid()) map.fitBounds(bounds, { padding: [42, 42], maxZoom: 15 });
      }
    });
    return () => cancelAnimationFrame(raf);
  }, [stops, route, activeId, onSelect]);

  // pan to the selected stop
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !activeId) return;
    const s = stops.find((x) => x.id === activeId);
    if (s) map.panTo([s.lat, s.lng], { animate: true });
  }, [activeId, stops]);

  return <div ref={elRef} className="itin-map" />;
}
