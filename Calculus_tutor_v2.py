import json
import re

def debug_calculus_json(file_path):
    print(f"--- '{file_path}' 디버깅 시작 ---")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = f.read()

        # 1. 보이지 않는 특수 공백(Zero-width space, Non-breaking space) 확인
        hidden_chars = re.findall(r'[\u00A0\u200b\u200c\u200d\ufeff]', raw_data)
        if hidden_chars:
            print(f"⚠️ 경고: {len(hidden_chars)}개의 보이지 않는 특수 문자가 발견되었습니다. 제거를 시도합니다.")
            raw_data = re.sub(r'[\u00A0\u200b\u200c\u200d\ufeff]', ' ', raw_data)

        # 2. 잘못된 백슬래시(Single Backslash) 패턴 찾기
        # JSON에서 허용되지 않는 백슬래시 조합(\l, \s, \f 등)을 찾습니다.
        invalid_escapes = re.findall(r'\\(?![\\"/bfnrtu])', raw_data)
        if invalid_escapes:
            print(f"⚠️ 경고: {len(invalid_escapes)}개의 잘못된 백슬래시 이스케이프가 발견되었습니다.")
            # 자동 교정: \ -> \\
            raw_data = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', raw_data)

        # 3. JSON 파싱 시도
        try:
            data = json.loads(raw_data)
            print("✅ 결과: JSON 형식이 이제 완벽합니다!")
            
            # 교정된 내용을 새 파일로 저장 (백업 후 덮어쓰기 권장)
            with open('calculus_problems_fixed.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("💾 교정된 파일이 'calculus_problems_fixed.json'으로 저장되었습니다.")
            
        except json.JSONDecodeError as e:
            print(f"❌ 실패: 여전히 문법 오류가 존재합니다.")
            print(f"📍 위치: {e.lineno}행 {e.colno}열")
            # 에러 주변 텍스트 출력
            lines = raw_data.split('\n')
            start = max(0, e.lineno - 2)
            end = min(len(lines), e.lineno + 1)
            for i in range(start, end):
                prefix = ">> " if i == e.lineno - 1 else "   "
                print(f"{i+1}{prefix}{lines[i]}")

    except Exception as e:
        print(f"❌ 파일 읽기 오류: {e}")

if __name__ == "__main__":
    debug_calculus_json('calculus_problems.json')
