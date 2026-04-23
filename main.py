import argparse
import time
import os
import extract_preconditions
from GPT_chat import GPT
from GPT_chat import readexistans
from Config import config
from SMT_Solver.SMT_verifier import SMT_verifier


def main(path2CFile, path2CFG, path2SMT, newfile):
    path = config.resultpath
    os.makedirs(os.path.join("Result", path), exist_ok=True)
    start_time = time.time()
    result_file_path = "Result/" + path + "/" + str(newfile) + ".txt"
    result_file = open(result_file_path, "w")
    GPT.reset_llm_usage_stats()
    sMT_verifier = SMT_verifier()
    solved = False
    CE = {'p': [],
          'n': [],
          'i': []}
    print("Begin_process:   ", path2CFile)
    result_file.write("Begin_process:   " + str(path2CFile) + '\n')
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
    result_file.write("LLM Answer: " + str(gptAnswer) + "\n")
    print("AnsSet: ", AnsSet)
    result_file.write("AnsSet: " + str(AnsSet) + '\n')

    def write_summary_metrics(total_time=None):
        llm_usage_stats = GPT.get_llm_usage_stats()
        smt_total_time = sMT_verifier.get_total_solver_time()
        if total_time is not None:
            print("Time cost is :  ", str(total_time))
            result_file.write("Time cost is :  " + str(total_time) + '\n')
        print("LLM total tokens is :  ", str(llm_usage_stats["total_tokens"]))
        result_file.write("LLM total tokens is :  " + str(llm_usage_stats["total_tokens"]) + '\n')
        print("SMT total time is :  ", str(smt_total_time))
        result_file.write("SMT total time is :  " + str(smt_total_time) + '\n')

    def finalize_result(total_time=None):
        write_summary_metrics(total_time)
        result_file.flush()
        result_file.close()

    while Iteration < len(PT):
        current_time = time.time()
        if current_time - start_time >= config.Limited_time:
            print("Loop invariant Inference is OOT")
            result_file.write("Loop invariant Inference is OOT" + '\n')
            finalize_result(current_time - start_time)
            return None, None, gptAnswer, None
        Can_I = PT[Iteration]
        try:
            print("Candidate: ", gptAnswer[Iteration])
            result_file.write("Candidate: " + str(gptAnswer[Iteration]) + '\n')
            print("SMTLIB2: ", Can_I)
            result_file.write("SMTLIB2: " + str(Can_I) + '\n')
            Can_I_smt = Can_I[7:-1]
            print(Can_I_smt)
            result_file.write(str(Can_I_smt) + '\n')
            Counter_example, istrue = sMT_verifier.verify(Can_I, path2SMT)
        except TimeoutError as OOT:  # Out Of Time
            print("Checking timeout")
            result_file.write("Checking timeout" + '\n')
            Iteration += 1
            Counter_example = None
            istrue = False
            continue
        if Counter_example is None and istrue:  # Bingo
            solved = True
            print("The answer is :  ", str(gptAnswer[Iteration]))
            result_file.write("The answer is :  " + str(gptAnswer[Iteration]) + '\n')
            current_time = time.time()
            print("The proposal times is :  ", str(counterNumber + 1))
            result_file.write("The proposal times is :  " + str(counterNumber + 1) + '\n')
            finalize_result(current_time - start_time)
            return current_time - start_time, gptAnswer[Iteration], gptAnswer, counterNumber + 1
        elif istrue:
            if Counter_example.assignment not in CE[Counter_example.kind]:
                CE[Counter_example.kind].append(Counter_example.assignment)
            print(Counter_example.kind, Counter_example.assignment)
            result_file.write(str(Counter_example.kind) + str(Counter_example.assignment) + '\n')
            counterNumber += 1
            print("Size of CE: ", counterNumber)
            result_file.write("Size of CE: " + str(counterNumber) + '\n')
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
                    result_file.write("LLM Answer: " + str(gptAnswer) + "\n")
                    print("AnsSet: ", AnsSet)
                    result_file.write("AnsSet: " + str(AnsSet) + '\n')
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
                    result_file.write("LLM Answer: " + str(gptAnswer) + "\n")
                    print("AnsSet: ", AnsSet)
                    result_file.write("AnsSet: " + str(AnsSet) + '\n')
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
                    result_file.write("LLM Answer: " + str(gptAnswer) + "\n")
                    print("AnsSet: ", AnsSet)
                    result_file.write("AnsSet: " + str(AnsSet) + '\n')

        if AnsSetChanged:
            Candidate, SMTLIB2 = GPT.translate_AnsSet_to_smtlib2(AnsSet)
            try:
                print("=================Verifivation Begin=================")
                result_file.write("=================Verifivation Begin=================\n")
                print("CombineCandidate: ", Candidate)
                result_file.write("CombineCandidate: " + str(Candidate) + '\n')
                print("CombineSMTLIB2: ", SMTLIB2)
                result_file.write("CombineSMTLIB2: " + str(SMTLIB2) + '\n')
                Can_I_smt = SMTLIB2[7:-1]
                print(Can_I_smt)
                result_file.write(str(Can_I_smt) + '\n')
                Counter_example, istrue = sMT_verifier.verify(SMTLIB2, path2SMT)
            except TimeoutError as OOT:  # Out Of Time
                print("Checking timeout")
                result_file.write("Checking timeout" + '\n')
            if Counter_example is None and istrue:  # Bingo
                print("Correct loop invariant\n")
                result_file.write("Correct loop invariant\n")
                print("=================Verifivation Compelete=================\n")
                result_file.write("=================Verifivation Compelete=================\n")
                solved = True
                print("The answer is :  ", str(Candidate))
                result_file.write("The answer is :  " + str(Candidate) + '\n')
                current_time = time.time()
                print("The proposal times is :  ", str(counterNumber + 1))
                result_file.write("The proposal times is :  " + str(counterNumber + 1) + '\n')
                finalize_result(current_time - start_time)
                return current_time - start_time, Candidate, gptAnswer, counterNumber + 1
            elif istrue:
                if Counter_example.assignment not in CE[Counter_example.kind]:
                    CE[Counter_example.kind].append(Counter_example.assignment)
                print(Counter_example.kind, Counter_example.assignment)
                result_file.write(str(Counter_example.kind) + str(Counter_example.assignment) + '\n')
                counterNumber += 1
                print("Size of CE: ", counterNumber)
                result_file.write("Size of CE: " + str(counterNumber) + '\n')
                print("=================Verifivation Compelete=================\n")
                result_file.write("=================Verifivation Compelete=================\n")
            AnsSetChanged = False
        Iteration += 1
        result_file.write('\n')
        result_file.flush()
    result_file.write("\n\n\n")
    finalize_result(time.time() - start_time)
    return None, None, gptAnswer, None
