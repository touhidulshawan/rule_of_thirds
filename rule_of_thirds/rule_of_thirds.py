from krita import (
    Krita,
    DockWidget,
    DockWidgetFactory,
    DockWidgetFactoryBase
)
import pykrita

# Use the Qt binding matching this Krita build.
if pykrita.qt_major_version() == 6:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QPushButton,
        QLabel, QHBoxLayout
    )
else:
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QPushButton,
        QLabel, QHBoxLayout
    )


LAYER_NAME = "__Rule_of_Thirds_Overlay__"


class RuleOfThirdsDocker(DockWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Rule of Thirds")

        self.document = None
        self.overlay = None
        self.canvas_width = 0
        self.canvas_height = 0

        self.info = QLabel("Open a document")
        self.dimensions = QLabel("")

        self.show_button = QPushButton("Show Grid")
        self.hide_button = QPushButton("Hide Grid")
        self.refresh_button = QPushButton("Refresh Grid")

        layout = QVBoxLayout()

        layout.addWidget(self.info)
        layout.addWidget(self.dimensions)
        layout.addWidget(self.show_button)
        layout.addWidget(self.hide_button)
        layout.addWidget(self.refresh_button)
        layout.addStretch()

        widget = QWidget()
        widget.setLayout(layout)
        self.setWidget(widget)

        self.show_button.clicked.connect(self.show_grid)
        self.hide_button.clicked.connect(self.hide_grid)
        self.refresh_button.clicked.connect(self.refresh_grid)

        self.set_buttons(False)

    def set_buttons(self, enabled):
        self.show_button.setEnabled(enabled)
        self.hide_button.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)

    def canvasChanged(self, canvas):

        self.document = Krita.instance().activeDocument()
        self.overlay = None

        if self.document is None:
            self.info.setText("Open a document")
            self.dimensions.setText("")
            self.set_buttons(False)
            return

        self.canvas_width = self.document.width()
        self.canvas_height = self.document.height()

        self.dimensions.setText(
            "Canvas: {} x {} px".format(
                self.canvas_width,
                self.canvas_height
            )
        )

        # Recover our existing overlay if present.
        self.overlay = self.find_overlay()

        if self.overlay:
            self.info.setText("Grid layer found")
        else:
            self.info.setText("Ready")

        self.set_buttons(True)

    def find_overlay(self):

        if self.document is None:
            return None

        matches = self.document.rootNode().findChildNodes(
            LAYER_NAME, True, False, "paintlayer"
        )

        if matches:
            return matches[0]

        return None

    def make_line(self, node, x, y, width, height):

        # RGB U8 data in Krita is stored as BGRA.
        # Orange-red grid with partial transparency.
        pixel = bytes([40, 180, 255, 190])

        data = pixel * (width * height)

        return node.setPixelData(
            data, x, y, width, height
        )

    def create_grid(self):

        if self.document is None:
            return False

        doc = self.document
        width = doc.width()
        height = doc.height()

        # Prevent duplicate grid layers.
        existing = self.find_overlay()
        
        if existing is not None:
            self.overlay = existing
            existing.setVisible(True)
            doc.refreshProjection()
            self.info.setText("Existing grid layer reused")
            return True

        # This implementation deliberately supports RGB U8
        # documents only, avoiding incorrect pixel formats.
        if doc.colorModel() != "RGBA" or doc.colorDepth() != "U8":
            self.info.setText(
                "Please convert document to RGB / 8-bit"
            )
            return False

        # Remember the currently selected layer.
        previous_node = doc.activeNode()

        # Create a separate transparent paint layer.
        node = doc.createNode(
            LAYER_NAME,
            "paintlayer"
        )

        if node is None:
            self.info.setText("Could not create grid layer")
            return False

        if not doc.rootNode().addChildNode(node, None):
            self.info.setText("Could not add grid layer")
            return False

        node.setOpacity(190)

        # Two-pixel lines.
        line_width = 2

        x1 = round(width / 3)
        x2 = round((width * 2) / 3)

        y1 = round(height / 3)
        y2 = round((height * 2) / 3)

        # Keep all coordinates within the canvas.
        x1 = max(0, min(width - line_width, x1))
        x2 = max(0, min(width - line_width, x2))
        y1 = max(0, min(height - line_width, y1))
        y2 = max(0, min(height - line_width, y2))

        success = True

        # Vertical lines.
        success &= self.make_line(
            node, x1, 0, line_width, height
        )

        success &= self.make_line(
            node, x2, 0, line_width, height
        )

        # Horizontal lines.
        success &= self.make_line(
            node, 0, y1, width, line_width
        )

        success &= self.make_line(
            node, 0, y2, width, line_width
        )

        if not success:
            node.remove()
            self.info.setText("Could not draw grid pixels")
            return False

        # Lock the overlay so brush strokes cannot alter it.
        node.setLocked(True)
        node.setVisible(True)

        # Return to the previously selected artwork layer.
        if previous_node:
            doc.setActiveNode(previous_node)

        doc.refreshProjection()

        self.overlay = node
        self.canvas_width = width
        self.canvas_height = height

        self.info.setText("Rule of Thirds is ON")

        return True

    def show_grid(self):

        if self.document is None:
            return

        if self.overlay is None:
            self.overlay = self.find_overlay()

        if self.overlay is None:
            self.create_grid()
        else:
            self.overlay.setVisible(True)
            self.document.refreshProjection()
            self.info.setText("Rule of Thirds is ON")

    def hide_grid(self):

        if self.document is None:
            return

        if self.overlay is None:
            self.overlay = self.find_overlay()

        if self.overlay:
            self.overlay.setVisible(False)
            self.document.refreshProjection()
            self.info.setText("Rule of Thirds is OFF")

    def refresh_grid(self):
    
        if self.document is None:
            return
    
        doc = self.document
    
        # Find the existing grid layer by its unique name.
        existing = self.find_overlay()
    
        if existing is not None:
            existing.remove()
            doc.waitForDone()
    
        # Clear the old reference.
        self.overlay = None
    
        # Check whether the old layer was actually removed.
        remaining = self.find_overlay()
    
        if remaining is not None:
            self.info.setText(
                "Could not remove old grid layer. Refresh cancelled."
            )
            return

        # Recalculate using the resized canvas dimensions.
        self.canvas_width = doc.width()
        self.canvas_height = doc.height()
    
        self.dimensions.setText(
            "Canvas: {} x {} px".format(
                self.canvas_width,
                self.canvas_height
            )
        )
    
        self.create_grid()

Krita.instance().addDockWidgetFactory(
    DockWidgetFactory(
        "rule_of_thirds_docker",
        DockWidgetFactoryBase.DockPosition.DockRight,
        RuleOfThirdsDocker
    )
)
