/* Fake data for the OCC dashboard kit.
 * Tracks real ARGOS field names: src/argos/data_gen/schemas.py + ui/dashboard.py
 * Korean Air-style fleet HL-registrations; 60-route subset; KST departures.
 */

const ROUTES = [
  { id: "ICN-JFK", origin: "ICN", dest: "JFK", oLat: 37.4691, oLon: 126.4505, dLat: 40.6413, dLon: -73.7781 },
  { id: "ICN-LAX", origin: "ICN", dest: "LAX", oLat: 37.4691, oLon: 126.4505, dLat: 33.9416, dLon: -118.4085 },
  { id: "ICN-NRT", origin: "ICN", dest: "NRT", oLat: 37.4691, oLon: 126.4505, dLat: 35.7720, dLon: 140.3929 },
  { id: "ICN-PEK", origin: "ICN", dest: "PEK", oLat: 37.4691, oLon: 126.4505, dLat: 40.0801, dLon: 116.5846 },
  { id: "ICN-HKG", origin: "ICN", dest: "HKG", oLat: 37.4691, oLon: 126.4505, dLat: 22.3080, dLon: 113.9185 },
  { id: "ICN-SIN", origin: "ICN", dest: "SIN", oLat: 37.4691, oLon: 126.4505, dLat: 1.3644,  dLon: 103.9915 },
  { id: "ICN-CDG", origin: "ICN", dest: "CDG", oLat: 37.4691, oLon: 126.4505, dLat: 49.0097, dLon: 2.5479  },
  { id: "ICN-LHR", origin: "ICN", dest: "LHR", oLat: 37.4691, oLon: 126.4505, dLat: 51.4700, dLon: -0.4543 },
  { id: "ICN-FRA", origin: "ICN", dest: "FRA", oLat: 37.4691, oLon: 126.4505, dLat: 50.0379, dLon: 8.5622  },
  { id: "ICN-SYD", origin: "ICN", dest: "SYD", oLat: 37.4691, oLon: 126.4505, dLat: -33.9399, dLon: 151.1753 },
];

const FLIGHTS = [
  { id: "f1",  num: "KE001", route: "ICN-JFK", reg: "HL7762", type: "B777-300ER", dep: "14:35", delay: 0,   pax: 287, status: "DEP" },
  { id: "f2",  num: "KE085", route: "ICN-LAX", reg: "HL8205", type: "B787-9",    dep: "16:10", delay: 12,  pax: 312, status: "DEP" },
  { id: "f3",  num: "KE703", route: "ICN-NRT", reg: "HL7411", type: "B737-800",  dep: "09:20", delay: 45,  pax: 168, status: "DLY" },
  { id: "f4",  num: "KE093", route: "ICN-PEK", reg: "HL8048", type: "A321neo",   dep: "11:55", delay: 0,   pax: 0,   status: "CNX" },
  { id: "f5",  num: "KE623", route: "ICN-HKG", reg: "HL7634", type: "B777-300ER",dep: "08:45", delay: 0,   pax: 264, status: "DEP" },
  { id: "f6",  num: "KE645", route: "ICN-SIN", reg: "HL8056", type: "B787-9",    dep: "23:50", delay: 18,  pax: 234, status: "DLY" },
  { id: "f7",  num: "KE901", route: "ICN-CDG", reg: "HL7644", type: "B777-300ER",dep: "13:05", delay: 0,   pax: 291, status: "DEP" },
  { id: "f8",  num: "KE907", route: "ICN-LHR", reg: "HL7766", type: "B777-300ER",dep: "12:40", delay: 0,   pax: 278, status: "DEP" },
  { id: "f9",  num: "KE905", route: "ICN-FRA", reg: "HL8221", type: "A321neo",   dep: "13:35", delay: 0,   pax: 184, status: "SCH" },
  { id: "f10", num: "KE121", route: "ICN-SYD", reg: "HL8002", type: "B787-9",    dep: "19:55", delay: 0,   pax: 222, status: "SCH" },
  { id: "f11", num: "KE603", route: "ICN-NRT", reg: "HL7415", type: "B737-800",  dep: "13:50", delay: 60,  pax: 156, status: "DLY" },
  { id: "f12", num: "KE629", route: "ICN-HKG", reg: "HL8211", type: "A321neo",   dep: "17:20", delay: 0,   pax: 178, status: "SCH" },
  { id: "f13", num: "KE741", route: "ICN-PEK", reg: "HL8044", type: "A321neo",   dep: "08:10", delay: 9,   pax: 162, status: "DEP" },
  { id: "f14", num: "KE647", route: "ICN-SIN", reg: "HL8067", type: "B787-9",    dep: "11:20", delay: 0,   pax: 240, status: "DEP" },
];

const KPIS = {
  totalFlights: 412,
  delayed: 37,
  cancelled: 2,
  paxToday: 94820,
  delayedDelta: "+8.9%",
  paxDelta: "−1.2%",
};

const VERTIPORTS = [
  { id: "ICN-T1", nameKo: "인천공항 T1", lat: 37.4549, lon: 126.4402, pads: 4 },
  { id: "ICN-T2", nameKo: "인천공항 T2", lat: 37.4463, lon: 126.4508, pads: 4 },
  { id: "GMP",    nameKo: "김포공항",   lat: 37.5583, lon: 126.7906, pads: 6 },
  { id: "YDP",    nameKo: "여의도",     lat: 37.5219, lon: 126.9244, pads: 8 },
  { id: "SBR",    nameKo: "송도",       lat: 37.3920, lon: 126.6476, pads: 4 },
  { id: "SWN",    nameKo: "수원",       lat: 37.2387, lon: 127.0065, pads: 4 },
  { id: "BDC",    nameKo: "판교",       lat: 37.3943, lon: 127.1110, pads: 4 },
];

const CORRIDORS = [
  { from: "ICN-T1", to: "ICN-T2", nm:  0.8, avoidsCTR: true  },
  { from: "ICN-T2", to: "SBR",    nm:  8.6, avoidsCTR: true  },
  { from: "SBR",    to: "YDP",    nm: 20.5, avoidsCTR: true  },
  { from: "YDP",    to: "GMP",    nm:  9.3, avoidsCTR: true  },
  { from: "GMP",    to: "ICN-T1", nm: 18.4, avoidsCTR: false },
  { from: "YDP",    to: "SWN",    nm: 18.2, avoidsCTR: true  },
  { from: "SWN",    to: "BDC",    nm: 12.0, avoidsCTR: true  },
  { from: "YDP",    to: "BDC",    nm: 11.8, avoidsCTR: true  },
];

// Recovery scenarios for trigger flight KE001 + 90 min delay
function buildScenarios(triggerNum, delayMin) {
  return [
    {
      id: 1,
      name: "수용",
      enName: "Accept",
      feas: "HIGH",
      ci: 0.32,
      desc: "현 스케줄 유지. 후속 회전 4편에 지연 전파.",
      action: `${triggerNum}을 ${delayMin}분 지연 출발로 기록. 후속 편 통보.`,
      residual: { legs: 4, delay: delayMin * 4, pax: 1210 },
    },
    {
      id: 2,
      name: "기재 교체",
      enName: "Aircraft swap",
      feas: "MEDIUM",
      ci: 0.58,
      desc: "동일 기종 HL8205 (대기 중) 으로 교체. CP-SAT 호환 시간 충돌 없음.",
      action: `${triggerNum} 등록 기재 HL7762 → HL8205. 운항 승무원 유지.`,
      residual: { legs: 1, delay: 30, pax: 287 },
    },
    {
      id: 3,
      name: "결항",
      enName: "Cancel",
      feas: "LOW",
      ci: 0.91,
      desc: "결항 후 후속 4편 회전 분리. 승객 287명 재예약 발생.",
      action: `${triggerNum} 결항. CNX 코드 90 (Operations) 부여. 후속 편 정상.`,
      residual: { legs: 0, delay: 0, pax: 287 },
    },
  ];
}

const CASCADE_CHAIN = ["KE001", "KE002", "KE085", "KE086", "KE092"];

// Delay distribution histogram (binned departure-delay minutes, count)
const DELAY_HIST = [42, 58, 47, 36, 29, 24, 18, 15, 12, 9, 7, 6, 5, 4, 3, 2, 2, 1, 1, 1];

Object.assign(window, { ROUTES, FLIGHTS, KPIS, VERTIPORTS, CORRIDORS, buildScenarios, CASCADE_CHAIN, DELAY_HIST });
