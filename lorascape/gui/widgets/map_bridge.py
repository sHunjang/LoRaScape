# lorascape/gui/widgets/map_bridge.py
"""
JavaScript <-> Python 브릿지임 (Leaflet 지도의 클릭/드래그 이벤트를 Qt 시그널로 전달).
JS 삽입 스크립트도 여기 같이 둠 - 브릿지 관련 코드는 한 파일에 모아두는 게
나중에 이벤트 종류 늘릴 때 찾기 편함.
"""
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot


class MapBridge(QObject):
    """JavaScript <-> Python 브릿지임 (클릭/드래그 이벤트 수신)."""
    clicked       = pyqtSignal(float, float)
    right_clicked = pyqtSignal(float, float)
    gw_dragged    = pyqtSignal(str, float, float)
    nd_dragged    = pyqtSignal(str, float, float)

    @pyqtSlot(float, float)
    def mapClicked(self, lon, lat):
        self.clicked.emit(lon, lat)

    @pyqtSlot(float, float)
    def mapRightClicked(self, lon, lat):
        self.right_clicked.emit(lon, lat)

    @pyqtSlot(str, float, float)
    def gwDragged(self, gw_id, lon, lat):
        self.gw_dragged.emit(gw_id, lon, lat)

    @pyqtSlot(str, float, float)
    def nodeDragged(self, node_id, lon, lat):
        self.nd_dragged.emit(node_id, lon, lat)


def webchannel_init_script() -> str:
    """페이지 로드 시 QWebChannel을 초기화하는 스크립트임. 매번 동일해서 상수처럼 씀."""
    return """
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
var _bridge = null;
new QWebChannel(qt.webChannelTransport, function(ch){
    _bridge = ch.objects.bridge;
});
</script>"""


def map_event_script(map_name: str) -> str:
    """
    Leaflet 지도 객체에 클릭/우클릭/드래그 이벤트 리스너를 붙이는 스크립트임.
    map_name은 folium이 생성한 지도 객체의 JS 변수명(m.get_name())임 - 매번 달라져서
    함수 인자로 받음.
    """
    return f"""
(function waitMap(){{
    var mapObj = window['{map_name}'];
    if(!mapObj){{ setTimeout(waitMap, 100); return; }}

    mapObj.on('click', function(e){{
        if(_bridge) _bridge.mapClicked(e.latlng.lng, e.latlng.lat);
    }});

    mapObj.on('contextmenu', function(e){{
        L.DomEvent.preventDefault(e);
        L.DomEvent.stopPropagation(e);
        if(_bridge) _bridge.mapRightClicked(e.latlng.lng, e.latlng.lat);
    }});

    mapObj.eachLayer(function(layer){{
        if(layer instanceof L.Marker && layer.options.draggable){{
            layer.on('dragend', function(e){{
                var ll = e.target.getLatLng();
                var tip = e.target.getTooltip();
                if(!tip) return;
                var content = tip.getContent();
                var text = content.replace(/<[^>]*>/g, '').trim();
                var id_ = text.split(' | ')[0].trim();
                if(content.indexOf('Pt=') !== -1){{
                    if(_bridge) _bridge.gwDragged(id_, ll.lng, ll.lat);
                }} else {{
                    if(_bridge) _bridge.nodeDragged(id_, ll.lng, ll.lat);
                }}
            }});
        }}
    }});
}})();"""