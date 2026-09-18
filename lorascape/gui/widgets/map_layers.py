# lorascape/gui/widgets/map_layers.py
"""
folium 지도에 레이어를 추가하는 순수 함수들임. Qt에 전혀 의존 안 해서
QApplication 없이도 단위테스트 가능함 (folium.Map 객체와 데이터만 있으면 됨).

map_widget.py의 MapWidget.refresh()가 이 함수들을 순서대로 호출해서
지도를 조립하는 구조임 - 레이어 하나하나가 뭘 그리는지는 여기서만 보면 됨.
"""
import math
import folium

GW_COLORS = [
    'red', 'blue', 'green', 'purple', 'orange',
    'darkred', 'darkblue', 'darkgreen', 'darkpurple', 'cadetblue',
    'pink', 'lightblue', 'lightgreen', 'beige', 'black',
]

PR_COLOR_LEVELS = [
    (-90,  '#FF2020'),
    (-100, '#FF8C00'),
    (-110, '#FFD700'),
    (-120, '#00C94A'),
    (-999, '#4f8ef7'),
]


def pr_to_color(pr: float) -> str:
    """수신전력(dBm)을 색상 hex 코드로 변환함."""
    for threshold, color in PR_COLOR_LEVELS:
        if pr >= threshold:
            return color
    return '#4f8ef7'


def build_gw_color_map(gws: list) -> dict:
    """활성화된 GW마다 순서대로 고유 색상을 배정함."""
    color_map = {}
    active_gws = [g for g in (gws or []) if g.enabled]
    for i, gw in enumerate(active_gws):
        color_map[gw.gw_id] = GW_COLORS[i % len(GW_COLORS)]
    return color_map


def _haversine_km(p1, p2) -> float:
    """p1, p2 = (lon, lat) 튜플임. 거리측정선 표시용 - core.coord_transform.distance_m과
    별개로 존재하는 이유: 이건 화면 표시용 근사치라 정밀도 요구가 낮고, Qt 레이어
    모듈이 core에 의존하지 않게 독립적으로 둠 (레이어 그리기는 순수 표시 로직이라서)."""
    R = 6371.0
    la1, lo1 = math.radians(p1[1]), math.radians(p1[0])
    la2, lo2 = math.radians(p2[1]), math.radians(p2[0])
    dlat = la2 - la1
    dlon = lo2 - lo1
    a = (math.sin(dlat / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def add_measure_layer(m: folium.Map, measure_pts: list):
    """거리 측정선 레이어를 추가함. measure_pts: [(lon, lat), ...]"""
    if not measure_pts or len(measure_pts) < 1:
        return

    for i, (lon, lat) in enumerate(measure_pts):
        folium.CircleMarker(
            location=[lat, lon], radius=6,
            color='#FFD700', fill=True, fill_color='#FFD700', fill_opacity=1.0,
            tooltip=f"P{i+1} ({lat:.5f}, {lon:.5f})",
        ).add_to(m)

    for i in range(len(measure_pts) - 1):
        p1, p2 = measure_pts[i], measure_pts[i + 1]
        dist = _haversine_km(p1, p2)
        folium.PolyLine(
            locations=[[p1[1], p1[0]], [p2[1], p2[0]]],
            color='#FFD700', weight=2.5, dash_array='8 4', opacity=0.9,
        ).add_to(m)
        mid_lat = (p1[1] + p2[1]) / 2
        mid_lon = (p1[0] + p2[0]) / 2
        folium.Marker(
            location=[mid_lat, mid_lon],
            icon=folium.DivIcon(
                html=f'''<div style="
                    background:#1e2130cc;color:#FFD700;
                    border:1px solid #FFD700;border-radius:4px;
                    padding:2px 6px;font-size:11px;
                    font-weight:bold;white-space:nowrap;
                    ">{dist:.3f} km</div>''',
                icon_size=(90, 24), icon_anchor=(45, 12),
            ),
        ).add_to(m)


def add_heatmap_layers(m: folium.Map, heatmaps: list, hm_opacity: float):
    """
    격자 히트맵 이미지 / 등고선 / SF 레이어를 추가함.
    heatmaps는 별도 워커가 미리 계산해서 넘겨주는 데이터임 - 여기선 그리기만 함.
    """
    if not heatmaps:
        return

    for hm in heatmaps:
        hm_type = hm.get('type', '')

        if 'url' in hm:
            lyr_name = (f"{hm['gw_id']} 히트맵" if hm_type == 'env_map'
                        else f"{hm['gw_id']} 전파 세기 (격자)")
            lyr = folium.FeatureGroup(name=lyr_name, show=True)
            folium.raster_layers.ImageOverlay(
                image=hm['url'], bounds=hm['bounds'],
                opacity=hm_opacity, interactive=False,
                cross_origin=False, zindex=2,
            ).add_to(lyr)
            lyr.add_to(m)

        if 'contours' in hm:
            for cl in hm['contours']:
                cl_lyr = folium.FeatureGroup(name=f"{hm['gw_id']} {cl['label']} 등고선", show=False)
                for seg in cl['segments']:
                    folium.PolyLine(
                        locations=seg, color=cl['color'], weight=cl['weight'],
                        opacity=0.9, tooltip=cl['label'], dash_array='6 4',
                    ).add_to(cl_lyr)
                for lp in cl.get('label_pts', []):
                    lh = (f'<div style="background:{cl["color"]}22;'
                          f'border:1px solid {cl["color"]};'
                          f'border-radius:4px;padding:1px 5px;'
                          f'font-size:10px;font-weight:bold;'
                          f'color:{cl["color"]};white-space:nowrap;'
                          f'pointer-events:none;">{lp["text"]}</div>')
                    folium.Marker(
                        location=[lp['lat'], lp['lon']],
                        icon=folium.DivIcon(html=lh, icon_size=(70, 20), icon_anchor=(35, 10)),
                    ).add_to(cl_lyr)
                cl_lyr.add_to(m)

        if 'sf_layers' in hm:
            for sl in hm['sf_layers']:
                sf_lyr = folium.FeatureGroup(name=f"{hm['gw_id']} {sl['label']}", show=False)
                for seg in sl['segments']:
                    folium.PolyLine(
                        locations=seg, color=sl['color'], weight=2.5,
                        opacity=0.85, tooltip=sl['label'], dash_array='8 4',
                    ).add_to(sf_lyr)
                sf_lyr.add_to(m)


def add_coverage_layers(m: folium.Map, nodes: list, result, selected_gws, cov_opacity: float):
    """
    커버리지 분석 결과 기반 레이어 3개(수신전력분포/중첩커버/음영지역)를 추가함.
    result: lorascape.core.optimization.gw_placement.OptimizationResult
    """
    if not result or not nodes:
        return

    cov_hm_lyr = folium.FeatureGroup(name="수신전력 분포 (분석 결과)", show=True)
    for nd in nodes:
        conn = result.connections.get(nd.node_id)
        if conn is None:
            continue
        if selected_gws and conn.gw_id not in selected_gws:
            continue

        pr = conn.rx_power_dbm
        color = pr_to_color(pr)
        n_rx = len(result.node_gw_ids.get(nd.node_id, []))
        tip = f"{nd.node_id} | Pr={pr:.1f}dBm | 연결 GW: {conn.gw_id} | 수신 GW: {n_rx}개"
        radius = max(14, min(22, int(14 + (pr + 120) / 5)))

        folium.CircleMarker(
            location=[nd.lat, nd.lon], radius=radius,
            color=color, fill=True, fill_color=color,
            fill_opacity=cov_opacity, weight=0, tooltip=tip,
        ).add_to(cov_hm_lyr)
    cov_hm_lyr.add_to(m)

    ovlp_lyr = folium.FeatureGroup(name="중첩 커버 영역", show=False)
    for nd in nodes:
        conn = result.connections.get(nd.node_id)
        n_rx = len(result.node_gw_ids.get(nd.node_id, []))
        if conn is not None and n_rx >= 2:
            radius = 18 + (n_rx - 2) * 6
            tip = f"{nd.node_id} | 중첩 커버 | 수신 GW: {n_rx}개 | Pr={conn.rx_power_dbm:.1f}dBm"
            folium.CircleMarker(
                location=[nd.lat, nd.lon], radius=radius,
                color='#9B59B6', fill=True, fill_color='#9B59B6',
                fill_opacity=0.25, weight=1.5, tooltip=tip,
            ).add_to(ovlp_lyr)
    ovlp_lyr.add_to(m)

    shadow_lyr = folium.FeatureGroup(name="음영 지역 (미커버)", show=False)
    for nd in nodes:
        conn = result.connections.get(nd.node_id)
        if conn is None:
            tip = f"{nd.node_id} | ✗ 미커버"
            folium.CircleMarker(
                location=[nd.lat, nd.lon], radius=10,
                color='#FF4444', fill=True, fill_color='#FF4444',
                fill_opacity=0.30, weight=1.5, tooltip=tip,
            ).add_to(shadow_lyr)
    shadow_lyr.add_to(m)


def add_node_marker_layer(m: folium.Map, nodes: list, result, gw_color_map: dict, selected_gws):
    """Node 마커 레이어를 추가함 (드래그 가능)."""
    if not nodes:
        return

    nd_lyr = folium.FeatureGroup(name="Nodes", show=True)
    filtering = bool(selected_gws)
    sel_set = set(selected_gws) if selected_gws else set()

    for nd in nodes:
        conn = result.connections.get(nd.node_id) if result else None
        if conn is not None:
            n_rx = len(result.node_gw_ids.get(nd.node_id, []))
            tip = (f"{nd.node_id} | ✓ 커버 | Pr={conn.rx_power_dbm:.1f}dBm | "
                   f"연결 GW: {conn.gw_id} ({n_rx}개 수신)")
            marker_color = gw_color_map.get(conn.gw_id, 'gray')
            is_selected_link = conn.gw_id in sel_set
        elif result:
            tip = f"{nd.node_id} | ✗ 미커버"
            marker_color = 'gray'
            is_selected_link = False
        else:
            marker_color = 'gray'
            tip = nd.node_id
            is_selected_link = False

        if filtering and not is_selected_link:
            marker_color = 'lightgray'
            opacity = 0.35
        else:
            opacity = 1.0

        folium.Marker(
            location=[nd.lat, nd.lon], tooltip=tip,
            icon=folium.Icon(color=marker_color, icon_color='white', icon='mobile', prefix='fa'),
            draggable=True, opacity=opacity,
        ).add_to(nd_lyr)
    nd_lyr.add_to(m)


def add_gw_marker_layer(m: folium.Map, gws: list, result, gw_color_map: dict):
    """GW 마커 레이어를 추가함 (드래그 가능)."""
    if not gws:
        return

    gw_lyr = folium.FeatureGroup(name="Gateway", show=True)
    for gw in gws:
        if not gw.enabled:
            continue
        marker_color = gw_color_map.get(gw.gw_id, 'gray')
        cnt = result.gw_counts.get(gw.gw_id, 0) if result else 0
        tip = (f"{gw.gw_id} | Pt={gw.tx_power_dbm}dBm Gt={gw.antenna_gain_dbi}dBi "
               f"h={gw.antenna_height_m}m | 담당 Node: {cnt}개")
        folium.Marker(
            location=[gw.lat, gw.lon], tooltip=tip,
            icon=folium.Icon(color=marker_color, icon_color='white', icon='broadcast-tower', prefix='fa'),
            draggable=True,
        ).add_to(gw_lyr)
    gw_lyr.add_to(m)


def add_field_data_layer(m: folium.Map, field_data: list):
    """실측 데이터 오버레이 레이어를 추가함. field_data: [{'lat','lon','rssi','snr'}, ...]"""
    if not field_data:
        return

    fd_lyr = folium.FeatureGroup(name="📡 실측 데이터", show=True)
    for pt in field_data:
        lat, lon = pt.get('lat', 0.0), pt.get('lon', 0.0)
        rssi = pt.get('rssi', -999.0)
        snr = pt.get('snr', None)
        color = pr_to_color(rssi)
        tip_parts = [f"실측 RSSI: {rssi:.1f} dBm"]
        if snr is not None:
            tip_parts.append(f"SNR: {snr:.1f} dB")
        tip = " | ".join(tip_parts)
        folium.CircleMarker(
            location=[lat, lon], radius=8, color='white', weight=2,
            fill=True, fill_color=color, fill_opacity=0.85, tooltip=tip,
        ).add_to(fd_lyr)
    fd_lyr.add_to(m)