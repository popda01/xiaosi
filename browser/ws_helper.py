import time
import random
from playwright.sync_api import Page, FrameLocator


def get_preview_frame(page: Page, logger=None) -> FrameLocator:
    """
    获取预览iframe的FrameLocator。
    """
    try:
        frame = page.frame_locator('iframe[title="Preview"]')
        return frame
    except Exception as e:
        if logger:
            logger.warning(f"获取Preview iframe失败: {e}")
        return None


def get_ws_status(page: Page, logger=None) -> str:
    """
    获取页面中WS连接状态（在iframe内部）。
    返回: CONNECTED, IDLE, CONNECTING 或 UNKNOWN
    """
    try:
        frame = get_preview_frame(page, logger)
        if not frame:
            return "UNKNOWN"

        status_element = frame.locator('text=/WS:\\s*(CONNECTED|IDLE|CONNECTING)/i').first
        if status_element.is_visible(timeout=3000):
            text = status_element.text_content()
            if text:
                if "CONNECTED" in text.upper():
                    return "CONNECTED"
                elif "IDLE" in text.upper():
                    return "IDLE"
                elif "CONNECTING" in text.upper():
                    return "CONNECTING"
        return "UNKNOWN"
    except Exception as e:
        if logger:
            logger.warning(f"获取WS状态时出错: {e}")
        return "UNKNOWN"


def click_disconnect(page: Page, logger=None) -> bool:
    """
    点击Disconnect按钮断开WS连接（在iframe内部）。
    """
    try:
        frame = get_preview_frame(page, logger)
        if not frame:
            return False

        disconnect_btn = frame.locator('button:has-text("Disconnect")')
        if disconnect_btn.count() > 0 and disconnect_btn.first.is_visible(timeout=3000):
            disconnect_btn.first.click(timeout=5000)
            if logger:
                logger.info("已点击 Disconnect 按钮")
            time.sleep(1)
            return True
        if logger:
            logger.warning("未找到可见的 Disconnect 按钮")
        return False
    except Exception as e:
        if logger:
            logger.warning(f"点击 Disconnect 按钮失败: {e}")
        return False


def click_connect(page: Page, logger=None) -> bool:
    """
    点击Connect按钮建立WS连接（在iframe内部）。
    """
    try:
        frame = get_preview_frame(page, logger)
        if not frame:
            return False

        connect_btn = frame.locator('button:has-text("Connect")')
        if connect_btn.count() > 0 and connect_btn.first.is_visible(timeout=3000):
            connect_btn.first.click(timeout=5000)
            if logger:
                logger.info("已点击 Connect 按钮")
            time.sleep(1)
            return True
        if logger:
            logger.warning("未找到可见的 Connect 按钮")
        return False
    except Exception as e:
        if logger:
            logger.warning(f"点击 Connect 按钮失败: {e}")
        return False


def wait_for_ws_connected(page: Page, logger=None, timeout: int = 30) -> bool:
    """
    等待WS状态变为CONNECTED。
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        status = get_ws_status(page, logger)
        if status == "CONNECTED":
            return True
        time.sleep(1)
    return False


def reconnect_ws(page: Page, logger=None) -> str:
    """
    执行断开再连接的流程，并返回最终WS状态。
    流程：关闭遮罩 -> Disconnect -> 等待IDLE -> Connect -> 等待CONNECTED -> 获取状态
    """
    if logger:
        logger.info("开始执行WS重连流程: Disconnect -> Connect")

    dismiss_interaction_modal(page, logger)
    click_disconnect(page, logger)
    time.sleep(2)

    status = get_ws_status(page, logger)
    if logger:
        logger.info(f"断开后WS状态: {status}")

    click_connect(page, logger)
    time.sleep(2)

    if wait_for_ws_connected(page, logger, timeout=15):
        status = get_ws_status(page, logger)
        if logger:
            logger.info(f"重连后WS状态: {status}")
        return status
    else:
        status = get_ws_status(page, logger)
        if logger:
            logger.warning(f"WS重连超时，当前状态: {status}")
        return status


def dismiss_interaction_modal(page: Page, logger=None) -> bool:
    """
    检测并关闭 interaction-modal 遮罩层。
    策略：鼠标移动 -> 点击iframe区域 -> 点击遮罩自身，逐级升级。

    返回: True 如果成功关闭遮罩，False 如果未找到遮罩或关闭失败
    """
    try:
        modal = page.locator('div.interaction-modal')
        if modal.count() == 0 or not modal.first.is_visible(timeout=500):
            return False

        if logger:
            logger.info("检测到 interaction-modal 遮罩层，尝试关闭...")

        iframe = page.locator('iframe[title="Preview"]')
        if iframe.count() > 0:
            iframe_box = iframe.first.bounding_box()
            if iframe_box:
                curr_x = iframe_box['x'] + random.randint(50, int(iframe_box['width']) - 50)
                curr_y = iframe_box['y'] + random.randint(50, int(iframe_box['height']) - 50)

                # 第一步：鼠标移动（最多10次，原版30次效率太低）
                for i in range(10):
                    delta_x = random.randint(-30, 30)
                    delta_y = random.randint(-20, 20)
                    curr_x = max(iframe_box['x'] + 20,
                                 min(iframe_box['x'] + iframe_box['width'] - 20, curr_x + delta_x))
                    curr_y = max(iframe_box['y'] + 20,
                                 min(iframe_box['y'] + iframe_box['height'] - 20, curr_y + delta_y))
                    page.mouse.move(curr_x, curr_y)
                    time.sleep(0.05)
                    if modal.count() == 0 or not modal.first.is_visible(timeout=100):
                        if logger:
                            logger.info("已通过鼠标移动关闭 interaction-modal 遮罩层")
                        return True

                # 第二步：移动无效，直接点击 iframe 区域
                if logger:
                    logger.info("鼠标移动无效，尝试直接点击关闭 interaction-modal...")
                page.mouse.click(curr_x, curr_y)
                time.sleep(0.5)
                if modal.count() == 0 or not modal.first.is_visible(timeout=500):
                    if logger:
                        logger.info("已通过点击 iframe 区域关闭 interaction-modal 遮罩层")
                    return True

                # 第三步：点击遮罩自身（部分弹窗点击自身即可关闭）
                try:
                    modal_box = modal.first.bounding_box()
                    if modal_box:
                        if logger:
                            logger.info("尝试点击遮罩自身关闭 interaction-modal...")
                        page.mouse.click(
                            modal_box['x'] + modal_box['width'] / 2,
                            modal_box['y'] + modal_box['height'] / 2
                        )
                        time.sleep(0.5)
                        if modal.count() == 0 or not modal.first.is_visible(timeout=500):
                            if logger:
                                logger.info("已通过点击遮罩自身关闭 interaction-modal")
                            return True
                except Exception:
                    pass

        if logger:
            logger.warning("无法关闭 interaction-modal，将在下次循环重试")
        return False

    except Exception as e:
        if logger:
            logger.debug(f"关闭 interaction-modal 时出错: {e}")
        return False


def click_in_iframe(page: Page, logger=None) -> bool:
    """
    在 iframe 内随机移动鼠标并点击一次，用于保活。
    避开顶部（状态栏和按钮区域）和右侧区域。

    返回: True 如果成功点击，False 如果失败
    """
    try:
        iframe = page.locator('iframe[title="Preview"]')
        if iframe.count() == 0:
            return False

        iframe_box = iframe.first.bounding_box()
        if not iframe_box:
            return False

        safe_left = iframe_box['x'] + 50
        safe_right = iframe_box['x'] + iframe_box['width'] - 200
        safe_top = iframe_box['y'] + 80
        safe_bottom = iframe_box['y'] + iframe_box['height'] - 50

        if safe_right <= safe_left or safe_bottom <= safe_top:
            return False

        curr_x = random.randint(int(safe_left), int(safe_right))
        curr_y = random.randint(int(safe_top), int(safe_bottom))

        for _ in range(random.randint(3, 6)):
            delta_x = random.randint(-30, 30)
            delta_y = random.randint(-20, 20)
            curr_x = max(int(safe_left), min(int(safe_right), curr_x + delta_x))
            curr_y = max(int(safe_top), min(int(safe_bottom), curr_y + delta_y))
            page.mouse.move(curr_x, curr_y)
            time.sleep(0.05)

        page.mouse.click(curr_x, curr_y)
        return True

    except Exception as e:
        if logger:
            logger.debug(f"在 iframe 内点击失败: {e}")
        return False
