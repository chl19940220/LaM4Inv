import argparse
import json
import time
import os
import tempfile
import extract_preconditions
from GPT_chat import GPT
from GPT_chat import readexistans
from Config import config
from SMT_Solver.SMT_verifier import SMT_verifier


def main(path2CFile, path2CFG, path2SMT, newfile):
    path = config.resultpath
    result_dir = os.path.abspath(os.path.join("Result", path))
    os.makedirs(result_dir, exist_ok=True)
    start_time = time.time()
    result_file_path = os.path.join(result_dir, f"{newfile}.json")
    GPT.reset_llm_usage_stats()
    sMT_verifier = SMT_verifier()
    solved = False
    CE = {'p': [],
          'n': [],
          'i': []}
    run_trace = []

    def write_line(line=""):
        run_trace.append(line)

    def persist_result(total_time, answer, proposal_times, candidate_smtlib2):
        llm_usage_stats = GPT.get_llm_usage_stats()
        smt_total_time = sMT_verifier.get_total_solver_time()
        result_payload = {
            "case_name": str(newfile),
            "case_path": path2CFile,
            "cfg_path": path2CFG,
            "smt_path": path2SMT,
            "verification_result": True,
            "answer": answer,
            "candidate_smtlib2": candidate_smtlib2,
            "time_cost": total_time,
            "proposal_times": proposal_times,
            "llm_total_tokens": llm_usage_stats["total_tokens"],
            "smt_total_time": smt_total_time,
            "llm_answers": gptAnswer,
            "ans_set": AnsSet,
            "trace": run_trace,
        }
        print("Time cost is :  ", str(total_time))
        print("LLM total tokens is :  ", str(llm_usage_stats["total_tokens"]))
        print("SMT total time is :  ", str(smt_total_time))
        with tempfile.NamedTemporaryFile("w", dir=result_dir, delete=False, suffix=".json") as temp_file:
            json.dump(result_payload, temp_file, ensure_ascii=False, indent=2)
            temp_file_path = temp_file.name
        os.replace(temp_file_path, result_file_path)

    print("Begin_process:   ", path2CFile)
    write_line("Begin_process:   " + str(path2CFile))
    Iteration = 0
    counterNumber = 0
    cFile = open(path2CFile)
    cProgramLines = cFile.readlines()
    cProgram = ""
    noPost = False
    for line in cProgramLines:
        if noPost and "assert" in line:
            continue
        if "while" in line:
            cProgram = cProgram + "//Line A" + "\n" + line + "//Line A" + "\n"
        else:
            cProgram = cProgram + line
    cFile.close()
    print(cProgram)
    gptAnswer = []
    PT = []
    AnsSet = []
    AnsSetChanged = False

    readexistanscount = 0
    existans = []
    if config.LLM == "Exist":
        existans = readexistans.readans("./Result/" + config.exsitresult + ".txt")
        existans = existans[path2CFile]

    preconditions = extract_preconditions.extract_preconditions(cProgram)
    pt, gptans, AnsSet = GPT.add_precondition(cProgram, preconditions)

    for i in range(5):
        lengthAnsSetbefore = len(AnsSet)
        pt, gptans, AnsSet = GPT.get_answer(cProgram, 0, "", "", AnsSet, existans, readexistanscount)
        readexistanscount += 1
        lengthAnsSetafter = len(AnsSet)
        AnsSetChanged = (lengthAnsSetafter != lengthAnsSetbefore) or AnsSetChanged
        for count in range(len(gptans)):
            if gptans[count] not in gptAnswer:
                PT.append(pt[count])
                gptAnswer.append(gptans[count])
    print("LLM Answer: ", gptAnswer)
    write_line("LLM Answer: " + str(gptAnswer))
    print("AnsSet: ", AnsSet)
    write_line("AnsSet: " + str(AnsSet))

    while Iteration < len(PT):
        current_time = time.time()
        if current_time - start_time >= config.Limited_time:
            print("Loop invariant Inference is OOT")
            return None, None, gptAnswer, None
        Can_I = PT[Iteration]
        try:
            print("Candidate: ", gptAnswer[Iteration])
            write_line("Candidate: " + str(gptAnswer[Iteration]))
            print("SMTLIB2: ", Can_I)
            write_line("SMTLIB2: " + str(Can_I))
            Can_I_smt = Can_I[7:-1]
            print(Can_I_smt)
            write_line(str(Can_I_smt))
            Counter_example, istrue = sMT_verifier.verify(Can_I, path2SMT)
        except TimeoutError as OOT:  # Out Of Time
            print("Checking timeout")
            Iteration += 1
            Counter_example = None
            istrue = False
            continue
        if Counter_example is None and istrue:  # Bingo
            solved = True
            print("The answer is :  ", str(gptAnswer[Iteration]))
            write_line("The answer is :  " + str(gptAnswer[Iteration]))
            current_time = time.time()
            print("The proposal times is :  ", str(counterNumber + 1))
            write_line("The proposal times is :  " + str(counterNumber + 1))
            persist_result(current_time - start_time, gptAnswer[Iteration], counterNumber + 1, Can_I)
            return current_time - start_time, gptAnswer[Iteration], gptAnswer, counterNumber + 1
        elif istrue:
            if Counter_example.assignment not in CE[Counter_example.kind]:
                CE[Counter_example.kind].append(Counter_example.assignment)
            print(Counter_example.kind, Counter_example.assignment)
            write_line(str(Counter_example.kind) + str(Counter_example.assignment))
            counterNumber += 1
            print("Size of CE: ", counterNumber)
            write_line("Size of CE: " + str(counterNumber))
            if Counter_example.kind == "n" and len(PT) < 50:
                for i in range(0, 2):
                    lengthAnsSetbefore = len(AnsSet)
                    pt, gptans, AnsSet = GPT.get_answer(cProgram, 2, gptAnswer[Iteration],
                                                        str(Counter_example.assignment), AnsSet, existans,
                                                        readexistanscount)
                    readexistanscount += 1
                    lengthAnsSetafter = len(AnsSet)
                    AnsSetChanged = (lengthAnsSetafter != lengthAnsSetbefore) or AnsSetChanged
                    for count in range(len(gptans)):
                        if gptans[count] not in gptAnswer:
                            PT.append(pt[count])
                            gptAnswer.append(gptans[count])
                    print("LLM Answer: ", gptAnswer)
                    write_line("LLM Answer: " + str(gptAnswer))
                    print("AnsSet: ", AnsSet)
                    write_line("AnsSet: " + str(AnsSet))
            elif Counter_example.kind == "p" and len(PT) < 50:
                for i in range(0, 2):
                    lengthAnsSetbefore = len(AnsSet)
                    pt, gptans, AnsSet = GPT.get_answer(cProgram, 1, gptAnswer[Iteration],
                                                        str(Counter_example.assignment), AnsSet, existans,
                                                        readexistanscount)
                    readexistanscount += 1
                    lengthAnsSetafter = len(AnsSet)
                    AnsSetChanged = (lengthAnsSetafter != lengthAnsSetbefore) or AnsSetChanged
                    for count in range(len(gptans)):
                        if gptans[count] not in gptAnswer:
                            PT.append(pt[count])
                            gptAnswer.append(gptans[count])
                    print("LLM Answer: ", gptAnswer)
                    write_line("LLM Answer: " + str(gptAnswer))
                    print("AnsSet: ", AnsSet)
                    write_line("AnsSet: " + str(AnsSet))
            elif Counter_example.kind == "i" and len(PT) < 50:
                for i in range(0, 2):
                    lengthAnsSetbefore = len(AnsSet)
                    pt, gptans, AnsSet = GPT.get_answer(cProgram, 3, gptAnswer[Iteration],
                                                        str(Counter_example.assignment), AnsSet, existans,
                                                        readexistanscount)
                    readexistanscount += 1
                    lengthAnsSetafter = len(AnsSet)
                    AnsSetChanged = (lengthAnsSetafter != lengthAnsSetbefore) or AnsSetChanged
                    for count in range(len(gptans)):
                        if gptans[count] not in gptAnswer:
                            PT.append(pt[count])
                            gptAnswer.append(gptans[count])
                    print("LLM Answer: ", gptAnswer)
                    write_line("LLM Answer: " + str(gptAnswer))
                    print("AnsSet: ", AnsSet)
                    write_line("AnsSet: " + str(AnsSet))

        if AnsSetChanged:
            Candidate, SMTLIB2 = GPT.translate_AnsSet_to_smtlib2(AnsSet)
            try:
                print("=================Verifivation Begin=================")
                write_line("=================Verifivation Begin=================")
                print("CombineCandidate: ", Candidate)
                write_line("CombineCandidate: " + str(Candidate))
                print("CombineSMTLIB2: ", SMTLIB2)
                write_line("CombineSMTLIB2: " + str(SMTLIB2))
                Can_I_smt = SMTLIB2[7:-1]
                print(Can_I_smt)
                write_line(str(Can_I_smt))
                Counter_example, istrue = sMT_verifier.verify(SMTLIB2, path2SMT)
            except TimeoutError as OOT:  # Out Of Time
                print("Checking timeout")
                write_line("Checking timeout")
            if Counter_example is None and istrue:  # Bingo
                print("Correct loop invariant\n")
                write_line("Correct loop invariant")
                print("=================Verifivation Compelete=================\n")
                write_line("=================Verifivation Compelete=================")
                solved = True
                print("The answer is :  ", str(Candidate))
                write_line("The answer is :  " + str(Candidate))
                current_time = time.time()
                print("The proposal times is :  ", str(counterNumber + 1))
                write_line("The proposal times is :  " + str(counterNumber + 1))
                persist_result(current_time - start_time, Candidate, counterNumber + 1, SMTLIB2)
                return current_time - start_time, Candidate, gptAnswer, counterNumber + 1
            elif istrue:
                if Counter_example.assignment not in CE[Counter_example.kind]:
                    CE[Counter_example.kind].append(Counter_example.assignment)
                print(Counter_example.kind, Counter_example.assignment)
                write_line(str(Counter_example.kind) + str(Counter_example.assignment))
                counterNumber += 1
                print("Size of CE: ", counterNumber)
                write_line("Size of CE: " + str(counterNumber))
                print("=================Verifivation Compelete=================\n")
                write_line("=================Verifivation Compelete=================")
            AnsSetChanged = False
        Iteration += 1
        write_line()
    return None, None, gptAnswer, None
