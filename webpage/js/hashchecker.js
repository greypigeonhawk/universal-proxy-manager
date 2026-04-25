const translations = {
  zh: {
    title: "🔐 Hash Checker",
    fileLabel: "选择文件：",
    textLabel: "或者输入文本：",
    algoLabel: "选择算法：",
    calcBtn: "计算哈希",
    nameLabel: "文件名:",
    sizeLabel: "大小:",
    hashLabel: "哈希值:",
    timeLabel: "计算耗时:",
    stampLabel: "时间戳:",
    compareTitle: "🔎 哈希比对",
    compareBtn: "比较",
    themeBtn: "🌙 切换暗色主题",
    langBtn: "English"
  },
  en: {
    title: "🔐 Hash Checker",
    fileLabel: "Select File:",
    textLabel: "Or Enter Text:",
    algoLabel: "Select Algorithm:",
    calcBtn: "Calculate Hash",
    nameLabel: "File Name:",
    sizeLabel: "Size:",
    hashLabel: "Hash:",
    timeLabel: "Time Taken:",
    stampLabel: "Timestamp:",
    compareTitle: "🔎 Compare Hash",
    compareBtn: "Compare",
    themeBtn: "🌙 Toggle Dark Theme",
    langBtn: "中文"
  }
};

let currentLang = 'zh';
function toggleLang() {
  currentLang = currentLang === 'zh' ? 'en' : 'zh';
  const t = translations[currentLang];
  for (let key in t) {
    document.getElementById(key).innerText = t[key];
  }
}

function toggleTheme() {
  document.body.classList.toggle('dark-theme');
}

function formatBytes(bytes) {
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  if (bytes === 0) return '0 B';
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return (bytes / Math.pow(1024, i)).toFixed(2) + ' ' + sizes[i];
}

async function calculateHash() {
  const file = document.getElementById('fileInput').files[0];
  const text = document.getElementById('textInput').value;
  const algorithm = document.getElementById('algorithm').value;
  const progressBar = document.getElementById('progressBar');
  const startTime = performance.now();

  let hash;
  if (file) {
    document.getElementById('fileName').innerText = file.name;
    document.getElementById('fileSize').innerText = formatBytes(file.size);
    
    const chunkSize = 2 * 1024 * 1024; // 2MB 分片
    let offset = 0;
    let wordArray = CryptoJS.lib.WordArray.create();

    while (offset < file.size) {
      const slice = file.slice(offset, offset + chunkSize);
      const buffer = await slice.arrayBuffer();
      const wa = CryptoJS.lib.WordArray.create(new Uint8Array(buffer));
      wordArray = wordArray.concat(wa);

      offset += chunkSize;
      let percent = Math.min(100, Math.floor((offset / file.size) * 100));
      progressBar.style.width = percent + '%';
      progressBar.innerText = percent + '%';
    }

    // 单个算法计算
    hash = computeHash(wordArray, algorithm);

  } else if (text.trim()) {
    document.getElementById('fileName').innerText = currentLang === 'zh' ? '文本输入' : 'Text Input';
    document.getElementById('fileSize').innerText = text.length + (currentLang === 'zh' ? ' 字符' : ' chars');
    
    hash = computeHash(text, algorithm);

    progressBar.style.width = '100%';
    progressBar.innerText = '100%';
  } else {
    alert(currentLang === 'zh' ? '请上传文件或输入文本' : 'Please upload file or enter text');
    return;
  }

  const endTime = performance.now();
  document.getElementById('hashValue').innerText = hash.toString();
  document.getElementById('timeTaken').innerText = ((endTime - startTime) / 1000).toFixed(2) + (currentLang === 'zh' ? ' 秒' : ' s');
  document.getElementById('timestamp').innerText = new Date().toLocaleString();
}


function computeHash(input, algo) {
  switch(algo) {
    case 'MD5': return CryptoJS.MD5(input);
    case 'SHA-1': return CryptoJS.SHA1(input);
    case 'SHA-224': return CryptoJS.SHA224(input);
    case 'SHA-256': return CryptoJS.SHA256(input);
    case 'SHA-384': return CryptoJS.SHA384(input);
    case 'SHA-512': return CryptoJS.SHA512(input);
    case 'SHA3-224': return CryptoJS.SHA3(input, { outputLength: 224 });
    case 'SHA3-256': return CryptoJS.SHA3(input, { outputLength: 256 });
    case 'SHA3-384': return CryptoJS.SHA3(input, { outputLength: 384 });
    case 'SHA3-512': return CryptoJS.SHA3(input, { outputLength: 512 });
    case 'RIPEMD160': return CryptoJS.RIPEMD160(input);
    default: return CryptoJS.SHA256(input);
  }
}

function compareHash() {
  const inputHash = document.getElementById('compareInput').value.trim().toLowerCase();
  const currentHash = document.getElementById('hashValue').innerText.trim().toLowerCase();
  const result = document.getElementById('compareResult');

  if (!inputHash) {
    result.innerText = currentLang === 'zh' ? '请输入哈希值' : 'Please enter a hash value';
    return;
  }

  if (inputHash === currentHash) {
    result.innerHTML = '<span style="color:green; font-weight:bold;">✅ ' + (currentLang === 'zh' ? '匹配成功' : 'Match') + '</span>';
  } else {
    result.innerHTML = '<span style="color:red; font-weight:bold;">❌ ' + (currentLang === 'zh' ? '不匹配' : 'Mismatch') + '</span>';
  }
}

function copyHash(el, hashValue) {
    navigator.clipboard.writeText(hashValue).then(() => {
        el.classList.add("copied");
        el.textContent = "✔"; // 改成对勾
        setTimeout(() => {
            el.classList.remove("copied");
            el.textContent = "📋"; // 恢复原状
        }, 1500);
    });
}
