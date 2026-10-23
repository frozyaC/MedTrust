# Диаграмма сообщений MedTrust

## Основной сценарий: `POST /api/v1/query`

```drawio
<mxfile>
  <diagram id="63lHzfy6AMuG20ZEaWA6" name="Page-1">
    <mxGraphModel dx="2" dy="1" grid="0" gridSize="10" guides="1" tooltips="0" connect="0" arrows="0" fold="0" page="0" pageScale="1" pageWidth="850" pageHeight="1100" math="0" shadow="0">
      <root>
        <mxCell id="JmKR1KsBhbqJQ-RZKPLz-0" />
        <mxCell id="JmKR1KsBhbqJQ-RZKPLz-1" parent="JmKR1KsBhbqJQ-RZKPLz-0" />
        <UserObject label="" mermaidData="{&#xa;  &quot;data&quot;: &quot;sequenceDiagram\r\n    participant F as Frontend\r\n    participant A as FastAPI\r\n    participant R as RagService\r\n    participant M as ConversationMemory\r\n    participant DB as PostgreSQL/pgvector\r\n    participant E as Embeddings\r\n    participant S as SearXNG\r\n    participant G as GigaChat\r\n\r\n    F-&gt;&gt;A: POST /api/v1/query\\nquestion + patient + conversation_id\r\n    A-&gt;&gt;R: question, patient, top_k, conversation_id\r\n    R-&gt;&gt;M: загрузить историю диалога\r\n    M-&gt;&gt;DB: SELECT conversation/messages/memory\r\n    DB--&gt;&gt;M: история и summary\r\n    M--&gt;&gt;R: memory_context\r\n\r\n    R-&gt;&gt;E: создать embedding поискового запроса\r\n    E--&gt;&gt;R: vector\r\n    R-&gt;&gt;DB: dense search + PostgreSQL FTS + path retrieval\r\n    DB--&gt;&gt;R: Wiki-кандидаты и retrieval diagnostics\r\n\r\n    alt Wiki-контекста достаточно\r\n        R-&gt;&gt;G: вопрос + patient + Wiki-источники + memory\r\n    else Wiki-контекста недостаточно\r\n        R-&gt;&gt;S: GET /search?q=...&amp;format=json\r\n        S--&gt;&gt;R: web candidates\r\n        R-&gt;&gt;R: HTTPS, allowlist и relevance checks\r\n        R-&gt;&gt;G: вопрос + patient + Wiki + WEB-источники + memory\r\n    end\r\n\r\n    G--&gt;&gt;R: черновик ответа\r\n    R-&gt;&gt;R: safety, source attribution и citation checks\r\n    R-&gt;&gt;M: сохранить вопрос и ответ\r\n    M-&gt;&gt;DB: INSERT chat_messages / update memory\r\n    DB--&gt;&gt;M: сохранено\r\n    R--&gt;&gt;A: answer + sources + retrieval + usage\r\n    A--&gt;&gt;F: JSON-ответ&quot;,&#xa;  &quot;config&quot;: null&#xa;}" id="3WpGXgH8gSBNrdA03plR-0">
          <mxCell connectable="0" parent="JmKR1KsBhbqJQ-RZKPLz-1" style="group;transparentBounds=1;editIcon=1;lockedGroup=0;groupPadding=10;" vertex="1">
            <mxGeometry as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Frontend" mermaidId="n:F" mermaidBaseStyle="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Frontend" id="JmKR1KsBhbqJQ-RZKPLz-2">
          <mxCell parent="3WpGXgH8gSBNrdA03plR-0" style="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="1399" width="150" x="10" y="10" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="FastAPI" mermaidId="n:A" mermaidBaseStyle="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="FastAPI" id="JmKR1KsBhbqJQ-RZKPLz-3">
          <mxCell parent="3WpGXgH8gSBNrdA03plR-0" style="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="1399" width="150" x="482" y="10" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="RagService" mermaidId="n:R" mermaidBaseStyle="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="RagService" id="JmKR1KsBhbqJQ-RZKPLz-4">
          <mxCell parent="3WpGXgH8gSBNrdA03plR-0" style="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="1399" width="150" x="831" y="10" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="ConversationMemory" mermaidId="n:M" mermaidBaseStyle="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="ConversationMemory" id="JmKR1KsBhbqJQ-RZKPLz-5">
          <mxCell parent="3WpGXgH8gSBNrdA03plR-0" style="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="1399" width="150" x="1084" y="10" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="PostgreSQL/pgvector" mermaidId="n:DB" mermaidBaseStyle="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="PostgreSQL/pgvector" id="JmKR1KsBhbqJQ-RZKPLz-6">
          <mxCell parent="3WpGXgH8gSBNrdA03plR-0" style="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="1399" width="150" x="1425" y="10" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="Embeddings" mermaidId="n:E" mermaidBaseStyle="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="Embeddings" id="JmKR1KsBhbqJQ-RZKPLz-7">
          <mxCell parent="3WpGXgH8gSBNrdA03plR-0" style="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="1399" width="150" x="1625" y="10" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="SearXNG" mermaidId="n:S" mermaidBaseStyle="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="SearXNG" id="JmKR1KsBhbqJQ-RZKPLz-8">
          <mxCell parent="3WpGXgH8gSBNrdA03plR-0" style="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="1399" width="150" x="1825" y="10" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="GigaChat" mermaidId="n:G" mermaidBaseStyle="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" mermaidBaseValue="GigaChat" id="JmKR1KsBhbqJQ-RZKPLz-9">
          <mxCell parent="3WpGXgH8gSBNrdA03plR-0" style="html=1;shape=umlLifeline;perimeter=lifelinePerimeter;whiteSpace=wrap;container=1;dropTarget=0;collapsible=0;recursiveResize=0;outlineConnect=0;portConstraint=eastwest;newEdgeStyle={&quot;edgeStyle&quot;:&quot;elbowEdgeStyle&quot;,&quot;elbow&quot;:&quot;vertical&quot;,&quot;curved&quot;:0,&quot;rounded&quot;:0};lifelineDashed=0;strokeWidth=2;rounded=1;absoluteArcSize=1;arcSize=6;lifelineColor=light-dark(#9370DB,#cccccc);size=65;lifelineMirror=1;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;" vertex="1">
            <mxGeometry height="1399" width="150" x="2025" y="10" as="geometry" />
          </mxCell>
        </UserObject>
        <UserObject label="alt" mermaidId="n:f0" mermaidBaseStyle="html=1;shape=umlFrame;dashed=1;fixDash=1;dashPattern=2 2;strokeWidth=2;pointerEvents=0;dropTarget=0;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontSize=16;align=center;verticalAlign=middle;fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontColor=light-dark(#333333,#cccccc);height=20;width=50;" mermaidBaseValue="alt" id="JmKR1KsBhbqJQ-RZKPLz-10">
          <mxCell parent="3WpGXgH8gSBNrdA03plR-0" style="html=1;shape=umlFrame;dashed=1;fixDash=1;dashPattern=2 2;strokeWidth=2;pointerEvents=0;dropTarget=0;fillColor=light-dark(#ECECFF,#1f2020);strokeColor=light-dark(#9370DB,#cccccc);fontSize=16;align=center;verticalAlign=middle;fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontColor=light-dark(#333333,#cccccc);height=20;width=50;" vertex="1">
            <mxGeometry height="414" width="1394" x="806" y="525" as="geometry" />
          </mxCell>
        </UserObject>
        <mxCell id="JmKR1KsBhbqJQ-RZKPLz-11" parent="JmKR1KsBhbqJQ-RZKPLz-10" style="text;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;fontSize=16;fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontColor=light-dark(#333333,#cccccc);" value="[Wiki-контекста достаточно]" vertex="1">
          <mxGeometry height="16" width="1340" x="54" y="2" as="geometry" />
        </mxCell>
        <mxCell id="JmKR1KsBhbqJQ-RZKPLz-12" parent="JmKR1KsBhbqJQ-RZKPLz-10" style="shape=line;dashed=1;fixDash=1;dashPattern=2 2;strokeColor=light-dark(#9370DB,#cccccc);" vertex="1">
          <mxGeometry height="1" width="1394" y="121" as="geometry" />
        </mxCell>
        <mxCell id="JmKR1KsBhbqJQ-RZKPLz-13" parent="JmKR1KsBhbqJQ-RZKPLz-10" style="text;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;whiteSpace=wrap;fontSize=16;fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontColor=light-dark(#333333,#cccccc);" value="[Wiki-контекста недостаточно]" vertex="1">
          <mxGeometry height="16" width="1394" y="123" as="geometry" />
        </mxCell>
        <UserObject label="POST /api/v1/query&#xa;question + patient + conversation_id" mermaidId="e:F-&gt;A#0" mermaidBaseStyle="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="POST /api/v1/query&#xa;question + patient + conversation_id" id="JmKR1KsBhbqJQ-RZKPLz-14">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-2" style="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-3">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="321" y="119" />
              </Array>
              <mxPoint x="85" y="119" as="sourcePoint" />
              <mxPoint x="557" y="119" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="question, patient, top_k, conversation_id" mermaidId="e:A-&gt;R#0" mermaidBaseStyle="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="question, patient, top_k, conversation_id" id="JmKR1KsBhbqJQ-RZKPLz-15">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-3" style="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-4">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="732" y="163" />
              </Array>
              <mxPoint x="557" y="163" as="sourcePoint" />
              <mxPoint x="906" y="163" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="загрузить историю диалога" mermaidId="e:R-&gt;M#0" mermaidBaseStyle="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="загрузить историю диалога" id="JmKR1KsBhbqJQ-RZKPLz-16">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-4" style="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-5">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1033" y="207" />
              </Array>
              <mxPoint x="906" y="207" as="sourcePoint" />
              <mxPoint x="1159" y="207" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="SELECT conversation/messages/memory" mermaidId="e:M-&gt;DB#0" mermaidBaseStyle="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="SELECT conversation/messages/memory" id="JmKR1KsBhbqJQ-RZKPLz-17">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-5" style="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-6">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1330" y="251" />
              </Array>
              <mxPoint x="1159" y="251" as="sourcePoint" />
              <mxPoint x="1500" y="251" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="история и summary" mermaidId="e:DB-&gt;M#0" mermaidBaseStyle="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="история и summary" id="JmKR1KsBhbqJQ-RZKPLz-18">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-6" style="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-5">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1330" y="295" />
              </Array>
              <mxPoint x="1500" y="295" as="sourcePoint" />
              <mxPoint x="1159" y="295" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="memory_context" mermaidId="e:M-&gt;R#0" mermaidBaseStyle="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="memory_context" id="JmKR1KsBhbqJQ-RZKPLz-19">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-5" style="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-4">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1033" y="339" />
              </Array>
              <mxPoint x="1159" y="339" as="sourcePoint" />
              <mxPoint x="906" y="339" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="создать embedding поискового запроса" mermaidId="e:R-&gt;E#0" mermaidBaseStyle="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="создать embedding поискового запроса" id="JmKR1KsBhbqJQ-RZKPLz-20">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-4" style="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-7">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1303" y="383" />
              </Array>
              <mxPoint x="906" y="383" as="sourcePoint" />
              <mxPoint x="1700" y="383" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="vector" mermaidId="e:E-&gt;R#0" mermaidBaseStyle="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="vector" id="JmKR1KsBhbqJQ-RZKPLz-21">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-7" style="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-4">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1303" y="427" />
              </Array>
              <mxPoint x="1700" y="427" as="sourcePoint" />
              <mxPoint x="906" y="427" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="dense search + PostgreSQL FTS + path retrieval" mermaidId="e:R-&gt;DB#0" mermaidBaseStyle="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="dense search + PostgreSQL FTS + path retrieval" id="JmKR1KsBhbqJQ-RZKPLz-22">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-4" style="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-6">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1203" y="471" />
              </Array>
              <mxPoint x="906" y="471" as="sourcePoint" />
              <mxPoint x="1500" y="471" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="Wiki-кандидаты и retrieval diagnostics" mermaidId="e:DB-&gt;R#0" mermaidBaseStyle="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="Wiki-кандидаты и retrieval diagnostics" id="JmKR1KsBhbqJQ-RZKPLz-23">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-6" style="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-4">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1203" y="515" />
              </Array>
              <mxPoint x="1500" y="515" as="sourcePoint" />
              <mxPoint x="906" y="515" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="вопрос + patient + Wiki-источники + memory" mermaidId="e:R-&gt;G#0" mermaidBaseStyle="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="вопрос + patient + Wiki-источники + memory" id="JmKR1KsBhbqJQ-RZKPLz-24">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-4" style="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-9">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1503" y="600" />
              </Array>
              <mxPoint x="906" y="600" as="sourcePoint" />
              <mxPoint x="2100" y="600" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="GET /search?q=...&amp;format=json" mermaidId="e:R-&gt;S#0" mermaidBaseStyle="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="GET /search?q=...&amp;format=json" id="JmKR1KsBhbqJQ-RZKPLz-25">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-4" style="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-8">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1403" y="690" />
              </Array>
              <mxPoint x="906" y="690" as="sourcePoint" />
              <mxPoint x="1900" y="690" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="web candidates" mermaidId="e:S-&gt;R#0" mermaidBaseStyle="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="web candidates" id="JmKR1KsBhbqJQ-RZKPLz-26">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-8" style="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-4">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1403" y="744" />
              </Array>
              <mxPoint x="1900" y="744" as="sourcePoint" />
              <mxPoint x="906" y="744" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:R-&gt;R#0" mermaidBaseStyle="edgeStyle=none;curved=1;endArrow=block;endSize=9;verticalAlign=bottom;align=center;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="" id="JmKR1KsBhbqJQ-RZKPLz-27">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-4" style="edgeStyle=none;curved=1;endArrow=block;endSize=9;verticalAlign=bottom;align=center;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-4">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="941" y="845" />
                <mxPoint x="945" y="857" />
                <mxPoint x="941" y="869" />
              </Array>
              <mxPoint x="906" y="845" as="sourcePoint" />
              <mxPoint x="906" y="869" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <mxCell id="JmKR1KsBhbqJQ-RZKPLz-28" parent="3WpGXgH8gSBNrdA03plR-0" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;fontColor=light-dark(#333333,#cccccc);" value="HTTPS, allowlist и relevance checks" vertex="1">
          <mxGeometry height="18" width="200" x="806" y="821" as="geometry" />
        </mxCell>
        <UserObject label="вопрос + patient + Wiki + WEB-источники + memory" mermaidId="e:R-&gt;G#1" mermaidBaseStyle="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="вопрос + patient + Wiki + WEB-источники + memory" id="JmKR1KsBhbqJQ-RZKPLz-29">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-4" style="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-9">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1503" y="929" />
              </Array>
              <mxPoint x="906" y="929" as="sourcePoint" />
              <mxPoint x="2100" y="929" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="черновик ответа" mermaidId="e:G-&gt;R#0" mermaidBaseStyle="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="черновик ответа" id="JmKR1KsBhbqJQ-RZKPLz-30">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-9" style="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-4">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1503" y="983" />
              </Array>
              <mxPoint x="2100" y="983" as="sourcePoint" />
              <mxPoint x="906" y="983" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="" mermaidId="e:R-&gt;R#1" mermaidBaseStyle="edgeStyle=none;curved=1;endArrow=block;endSize=9;verticalAlign=bottom;align=center;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="" id="JmKR1KsBhbqJQ-RZKPLz-31">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-4" style="edgeStyle=none;curved=1;endArrow=block;endSize=9;verticalAlign=bottom;align=center;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-4">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="941" y="1074" />
                <mxPoint x="945" y="1086" />
                <mxPoint x="941" y="1098" />
              </Array>
              <mxPoint x="906" y="1074" as="sourcePoint" />
              <mxPoint x="906" y="1098" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <mxCell id="JmKR1KsBhbqJQ-RZKPLz-32" parent="3WpGXgH8gSBNrdA03plR-0" style="text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;fontSize=16;fontColor=light-dark(#333333,#cccccc);" value="safety, source attribution и citation checks" vertex="1">
          <mxGeometry height="18" width="200" x="806" y="1050" as="geometry" />
        </mxCell>
        <UserObject label="сохранить вопрос и ответ" mermaidId="e:R-&gt;M#1" mermaidBaseStyle="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="сохранить вопрос и ответ" id="JmKR1KsBhbqJQ-RZKPLz-33">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-4" style="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-5">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1033" y="1148" />
              </Array>
              <mxPoint x="906" y="1148" as="sourcePoint" />
              <mxPoint x="1159" y="1148" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="INSERT chat_messages / update memory" mermaidId="e:M-&gt;DB#1" mermaidBaseStyle="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="INSERT chat_messages / update memory" id="JmKR1KsBhbqJQ-RZKPLz-34">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-5" style="endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-6">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1330" y="1192" />
              </Array>
              <mxPoint x="1159" y="1192" as="sourcePoint" />
              <mxPoint x="1500" y="1192" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="сохранено" mermaidId="e:DB-&gt;M#1" mermaidBaseStyle="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="сохранено" id="JmKR1KsBhbqJQ-RZKPLz-35">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-6" style="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-5">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="1330" y="1236" />
              </Array>
              <mxPoint x="1500" y="1236" as="sourcePoint" />
              <mxPoint x="1159" y="1236" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="answer + sources + retrieval + usage" mermaidId="e:R-&gt;A#0" mermaidBaseStyle="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="answer + sources + retrieval + usage" id="JmKR1KsBhbqJQ-RZKPLz-36">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-4" style="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-3">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="732" y="1280" />
              </Array>
              <mxPoint x="906" y="1280" as="sourcePoint" />
              <mxPoint x="557" y="1280" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
        <UserObject label="JSON-ответ" mermaidId="e:A-&gt;F#0" mermaidBaseStyle="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" mermaidBaseValue="JSON-ответ" id="JmKR1KsBhbqJQ-RZKPLz-37">
          <mxCell edge="1" parent="3WpGXgH8gSBNrdA03plR-0" source="JmKR1KsBhbqJQ-RZKPLz-3" style="dashed=1;fixDash=1;dashPattern=3 3;endArrow=block;endSize=9;verticalAlign=bottom;edgeStyle=elbowEdgeStyle;elbow=vertical;curved=0;rounded=0;fontSize=16;labelBackgroundColor=none;strokeWidth=1.5;strokeColor=light-dark(#333333,#cccccc);fontColor=light-dark(#333333,#cccccc);fontFamily=Trebuchet MS,Verdana,Arial,sans-serif;" target="JmKR1KsBhbqJQ-RZKPLz-2">
            <mxGeometry relative="1" as="geometry">
              <Array as="points">
                <mxPoint x="321" y="1324" />
              </Array>
              <mxPoint x="557" y="1324" as="sourcePoint" />
              <mxPoint x="85" y="1324" as="targetPoint" />
            </mxGeometry>
          </mxCell>
        </UserObject>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>

```
## Сообщение запроса

```http
POST /api/v1/query
Content-Type: application/json
```

```json
{
  "question": "Куда записать пациента при травме?",
  "patient": {
    "age": 42,
    "sex": "женский",
    "contraindications": [],
    "anamnesis": null
  },
  "top_k": 5,
  "conversation_id": null
}
```

Модель запроса описана в `app/schemas/api.py` в классе `QueryRequest`.

## Сообщение ответа

Фактический ответ может содержать следующие группы данных:

```json
{
  "answer": "...",
  "sources": [],
  "retrieval": [],
  "retrieval_queries": [],
  "conversation_id": "...",
  "web_search_attempted": false,
  "web_search_used": false,
  "web_search_status": "not_attempted",
  "resource_usage": {},
  "answer_reviewed": true,
  "source_checks_passed": true
}
```

Точный набор полей следует проверять по фактическому JSON-ответу `/api/v1/query` и по реализации `RagService.answer`. Для стабильного внешнего контракта ответ рекомендуется оформить отдельной Pydantic-моделью и передать в `response_model` маршрута.

## Внутренние границы

В текущей реализации `RagService`, `ConversationMemory`, репозитории и клиенты внешних систем находятся внутри одного API-процесса. Поэтому вызов Python-метода между ними не является отдельным HTTP-сообщением.

Отдельными сетевыми взаимодействиями являются:

| Отправитель | Получатель | Протокол | Назначение |
| --- | --- | --- | --- |
| Frontend | FastAPI | HTTP/JSON | запросы пользователя и ответы |
| API | PostgreSQL/pgvector | PostgreSQL | история, память, поиск и индекс |
| API | SearXNG | HTTP/JSON | резервный web-search |
| API | GigaChat | HTTPS/JSON | генерация ответа |
| API | Embeddings provider | HTTPS/JSON | получение векторов |

## Как проверить диаграмму на работающей системе

1. Запустить `docker compose up -d db searxng api frontend`.
2. Открыть `http://localhost:8000/docs`.
3. Выполнить `POST /api/v1/query` через Swagger.
4. Сопоставить запрос и ответ с этой диаграммой.
5. Открыть логи:

```powershell
docker compose logs -f api
```

6. Для временной трассировки добавить в каждый внешний вызов `trace_id`, имя операции и длительность.
7. Для постоянной трассировки подключить OpenTelemetry и просматривать spans в Jaeger или Grafana Tempo.

## Связанные материалы

- [Проверка доступных API](API_Inspect.md)
- [Логическая архитектура системы](Описание-архитектуры-системы-MedTrust.md)
- [Web-search fallback](../docs/WEB_SEARCH.md)
