# 替换成你的乱码字符串
garbled = "flag���ɣ�"

# 核心：先按UTF-8转字节，再用GBK/GB2312解码（CTF高频组合）
try:
    # 第一步：乱码→UTF-8字节
    raw_bytes = garbled.encode('utf-8', errors='ignore')
    # 第二步：字节→GBK解码（优先试GBK，再试GB2312）
    flag_gbk = raw_bytes.decode('gbk', errors='replace')
    print(f"GBK还原结果：{flag_gbk}")
    
    # 反向验证：GBK→UTF-8（部分场景需要）
    flag_reverse = raw_bytes.decode('gbk').encode('gbk').decode('utf-8', errors='replace')
    print(f"反向GBK→UTF-8：{flag_reverse}")
except Exception as e:
    print(f"解码失败：{e}")
