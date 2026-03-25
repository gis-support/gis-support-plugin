from qgis.PyQt.QtCore import Qt, QSize, QRect
from qgis.PyQt.QtWidgets import QStyledItemDelegate, QApplication
from qgis.PyQt.QtGui import QColor, QPainter,  QBrush, QPen, QFontMetrics

class CommentDelegate(QStyledItemDelegate):
    """
    Klasa wykorzystywana do stylizacji QListView z ostatnią aktywnością do formy chatu
    """
    
    def _get_dpi_scale_factor(self):
        """
        Oblicza współczynnik skalowania na podstawie DPI
        Jako bazowe DPI wybrano 72 (na takim projektowano czat)
        """
        screen = QApplication.primaryScreen()
        if screen:
            logical_dpi = screen.logicalDotsPerInch()
            return logical_dpi / 72.0
        return 1.0
    
    def _scale_value(self, value):
        return int(value * self._get_dpi_scale_factor())
    
    def paint(self, painter: QPainter, option, index):

        message = index.data(Qt.ItemDataRole.DisplayRole)
        alignment_role = index.data(Qt.ItemDataRole.UserRole + 2)

        flags = Qt.TextFlag.TextWordWrap

        # skalowane wartości paddingu i promienia
        text_padding_horizontal = self._scale_value(15)
        text_padding_vertical = self._scale_value(10)
        border_radius = self._scale_value(10)
        side_margin = self._scale_value(10)

        max_bubble_width_ratio = 0.75

        # obliczanie prostokąta dla tekstu i dymka
        metrics = painter.fontMetrics()
        
        # szerokość dostępna dla tekstu wewnątrz dymka, zanim zacznie się zawijać
        max_text_width_in_bubble = int(option.rect.width() * max_bubble_width_ratio) - (text_padding_horizontal * 2)
        min_text_width = self._scale_value(100)
        if max_text_width_in_bubble < min_text_width:
            max_text_width_in_bubble = min_text_width

        temp_rect_for_text_calc = QRect(0, 0, max_text_width_in_bubble, 0)
        text_bound_rect = metrics.boundingRect(temp_rect_for_text_calc, flags, message)

        text_content_width = text_bound_rect.width()

        calculated_bubble_width = text_content_width + (text_padding_horizontal * 2)

        max_allowed_bubble_width = int(option.rect.width() * max_bubble_width_ratio)

        bubble_width = min(calculated_bubble_width, max_allowed_bubble_width)
        
        bubble_height = text_bound_rect.height() + (text_padding_vertical * 2)

        if bubble_width > int(option.rect.width() * max_bubble_width_ratio):
             bubble_width = int(option.rect.width() * max_bubble_width_ratio)

        # obliczanie pozycji dymka
        bubble_rect = QRect(option.rect.left(),
                            option.rect.top() + int((option.rect.height() - bubble_height) / 2),
                            bubble_width, bubble_height)

        if alignment_role == Qt.AlignmentFlag.AlignRight:
            bubble_rect.moveRight(option.rect.right() - side_margin)
        elif alignment_role == Qt.AlignmentFlag.AlignLeft:
            bubble_rect.setLeft(option.rect.left() + side_margin)
        else:
            bubble_rect.moveLeft(option.rect.left() + int((option.rect.width() - bubble_width) / 2))

        # rysowanie dymka
        background_color = index.data(Qt.ItemDataRole.BackgroundRole)
        if not background_color:
            background_color = QColor(240, 240, 240)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if alignment_role != Qt.AlignmentFlag.AlignCenter:
            painter.setBrush(QBrush(background_color))
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.drawRoundedRect(bubble_rect, border_radius, border_radius)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(Qt.PenStyle.NoPen)
        
        # rysowanie tekstu wewnątrz dymka
        text_draw_rect = QRect(bubble_rect.left() + text_padding_horizontal,
                               bubble_rect.top() + text_padding_vertical,
                               bubble_width - (text_padding_horizontal * 2),
                               bubble_height - (text_padding_vertical * 2))
        
        text_flags = Qt.TextFlag.TextWordWrap
        if alignment_role == Qt.AlignmentFlag.AlignRight:
            text_flags |= Qt.AlignmentFlag.AlignRight
        elif alignment_role == Qt.AlignmentFlag.AlignLeft:
            text_flags |= Qt.AlignmentFlag.AlignLeft
        else:
            text_flags |= Qt.AlignmentFlag.AlignCenter

        if alignment_role == Qt.AlignmentFlag.AlignCenter:
            painter.setPen(QPen(QColor(128, 128, 128)))
        else:
            painter.setPen(QPen(QColor(0, 0, 0)))

        painter.drawText(text_draw_rect, text_flags, message)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter.setPen(QPen(Qt.GlobalColor.black))

    def sizeHint(self, option, index):
        message = index.data(Qt.ItemDataRole.DisplayRole)
        metrics = QFontMetrics(QApplication.font())
        
        flags_for_bounding = Qt.TextFlag.TextWordWrap

        # skalowane wartości
        text_padding_horizontal = self._scale_value(15)
        text_padding_vertical = self._scale_value(10)
        overall_vertical_spacing = self._scale_value(10)

        max_bubble_width_ratio = 0.75 

        available_text_width_for_calc = int(option.rect.width() * max_bubble_width_ratio) - (text_padding_horizontal * 2)
        min_text_width = self._scale_value(100)
        if available_text_width_for_calc < min_text_width: 
            available_text_width_for_calc = min_text_width

        temp_rect_for_calculation = QRect(0, 0, available_text_width_for_calc, 0)

        text_bound_rect = metrics.boundingRect(temp_rect_for_calculation, flags_for_bounding, message)

        bubble_height = text_bound_rect.height() + (text_padding_vertical * 2)

        return QSize(option.rect.width(), bubble_height + overall_vertical_spacing)
