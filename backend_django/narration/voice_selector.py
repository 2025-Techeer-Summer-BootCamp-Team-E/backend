from narration.table.tts_voice_map import VOICE_SELECTION_TABLE
''' tts_voice_map.py에서 정의된 voice_id에 따라서 ElvenLabs에 요청 보낼 보이스 선택'''

''' 성별, 나이에 따라서 voice_id를 선택하는 함수'''
# 어린아이, 청소년, 노인 별로 나이 그룹을 나눔
def age_to_group(age: int) -> str:
    # if age <= 10:
    #     return "child"
    if age <= 10:
        return "teen"
    elif age <= 39:
        return "adult"
    else:
        return "senior"

''' voice_id를 선택하는 함수'''
# 매개변수로 성별과 나이를 받음
def get_voice_id(gender: str, age: int) -> str:
    # 입력 값 안전성 검사
    if not isinstance(gender, str) or not isinstance(age, int):
        raise ValueError(f"gender must be str and age must be int, got gender: {type(gender)}, age: {type(age)}")

    # gender 값 정규화 (공백 제거, None 체크)
    if gender is None:
        raise ValueError("gender cannot be None")
    
    gender = str(gender).strip()
    if not gender:
        raise ValueError("gender cannot be empty")

    # age 값 검사
    if age is None:
        raise ValueError("age cannot be None")

    # 캐릭터의 나이에 따라서 나이 그룹을 지정
    age_group = age_to_group(age) # ex. age_to_group(20) = "adult"
    
    # 디버깅 출력
    print(f"Looking for voice: gender='{gender}', age={age}, age_group='{age_group}'") # 캐릭터의 성별, 나이, 나이 그룹 출력
    print(f"Available keys in VOICE_SELECTION_TABLE: {list(VOICE_SELECTION_TABLE.keys())}") # VOICE_SELECTION_TABLE에 따른 voice_id 출력
    
    # 성별과 나이 그룹에 따라서 voice_id를 선택
    voice_id = VOICE_SELECTION_TABLE.get((gender, age_group))
    
    # voice_id가 없으면 출력
    if not voice_id:
        print(f"No voice found for ({gender}, {age_group})")
    
    # 에러가 없으면 캐릭터 성별과 나이 그룹에 맞는 voice_id를 반환
    return voice_id

