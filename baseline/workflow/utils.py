import os
import base64

def img_to_img_url(img_path: str) -> str:
    """将图片转换为image_url
    
    支持jpg、png、jpeg格式
    
    Args:
        img_path: 图片文件路径
        
    Returns:
        str: 图片的data URL
        
    Raises:
        ValueError: 如果图片不存在或格式不支持
    """
    if not os.path.exists(img_path):
        raise ValueError(f"图片文件不存在: {img_path}")
        
    # 获取文件扩展名并确定mime type
    ext = os.path.splitext(img_path)[1].lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png'
    }
    
    if ext not in mime_types:
        raise ValueError(f"不支持的图片格式: {ext}，仅支持 {', '.join(mime_types.keys())}")
    
    try:
        with open(img_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
        # 检查编码字符串是否为空或太短
        if not encoded_string or len(encoded_string) < 10:
            error_msg = f"图片编码为空或太短: {img_path}, 长度: {len(encoded_string) if encoded_string else 0}"
            raise ValueError(error_msg)
            
        return f"data:{mime_types[ext]};base64,{encoded_string}"
    except Exception as e:
        error_msg = f"读取图片文件失败: {str(e)}"
        raise ValueError(error_msg)
