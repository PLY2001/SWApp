#include "Application.h"
#include "imgui.h"




namespace MyApp {

	//必须使用CComPtr来定义智能指针
	CComPtr<ISldWorks> swApp;// COM Pointer of Soldiworks object
	CComPtr<IModelDoc2> swDoc;// COM Pointer of Soldiworks Model Document
	CComPtr<ISelectionMgr> swSelectionManager;//选择物体
	CComPtr<IDispatch> swDispatch;//所有东西的父类
	CComPtr<IDimXpertManager> swDimXpert;//MBD
	CComPtr<IAnnotation> swAnnotation;//标注

	HRESULT result = NOERROR; //存储函数的输出结果		
	//CComBSTR _messageToUser;// COM Style String for message to user
	//long _lMessageResult;// long type variable to store the result value by user

	

	void MyApplication::ShowMyApp()
    {
		EnableDocking(); //开启Docking特性
		//ShowImguiExample();
		//ImGui::ShowDemoWindow();

		
		
		


        ImGui::Begin("SolidWorks API");                          // Create a window called "Hello, world!" and append into it.

        ImGui::Text("%.3f ms/frame (%.1f FPS)", 1000.0f / ImGui::GetIO().Framerate, ImGui::GetIO().Framerate);

		
		//SWBotton("连接SW", SWState::Connected, ConnectSW);
		//SWBotton("打开文件", SWState::FileOpen, OpenFile);
		//SWBotton("读取属性", SWState::PropertyGot, ReadProperty);
		if (ImGui::Button("连接SW")) {
			
			myState = ConnectSW() ? MyState::Succeed : MyState::Failed;
			SWStateMap[SWState::Connected] = myState;
			ImGui::OpenPopup("提示");
		}
		ImGui::SameLine();
		ImGui::Text(MyStateMessage[(int)SWStateMap[SWState::Connected]].c_str());

		if (ImGui::Button("打开文件")) {
			if (SWStateMap[SWState::Connected] == MyState::Succeed) {
				myState = OpenFile() ? MyState::Succeed : MyState::Failed;
				SWStateMap[SWState::FileOpen] = myState;
			}
			else {
				myState = MyState::Nothing;
				SWStateMap[SWState::FileOpen] = myState;
			}
			ImGui::OpenPopup("提示");
		}
		ImGui::SameLine();
		ImGui::Text(MyStateMessage[(int)SWStateMap[SWState::FileOpen]].c_str());

		if (ImGui::Button("读取属性")) {
			if (SWStateMap[SWState::Connected] == MyState::Succeed && SWStateMap[SWState::FileOpen] == MyState::Succeed) {
				myState = ReadProperty() ? MyState::Succeed : MyState::Failed;
				SWStateMap[SWState::PropertyGot] = myState;
			}
			else
			{
				myState = MyState::Nothing;
				SWStateMap[SWState::PropertyGot] = myState;
			}
			ImGui::OpenPopup("提示");
		}
		ImGui::SameLine();
		ImGui::Text(MyStateMessage[(int)SWStateMap[SWState::PropertyGot]].c_str());

		
		ShowMessage(MyStateMessage[(int)myState].c_str());

		
		//显示属性
		if (hasProperty) {
			ImGui::Separator();
			for (auto p : property) {
				std::string m = p.first + ":";
				m = m + p.second;
				ImGui::Text(m.c_str());
			}
			for (auto s : summary) {
				std::string m = s.first + s.second;
				ImGui::Text(m.c_str());
			}
		}
		

        ImGui::End();

        


		

    }





    void  MyApplication::EnableDocking()
    {
        
        static bool opt_fullscreen = true;
        static bool opt_padding = false;
        static ImGuiDockNodeFlags dockspace_flags = ImGuiDockNodeFlags_None;

        // We are using the ImGuiWindowFlags_NoDocking flag to make the parent window not dockable into,
        // because it would be confusing to have two docking targets within each others.
        ImGuiWindowFlags window_flags = ImGuiWindowFlags_MenuBar | ImGuiWindowFlags_NoDocking;
        if (opt_fullscreen)
        {
            const ImGuiViewport* viewport = ImGui::GetMainViewport();
            ImGui::SetNextWindowPos(viewport->WorkPos);
            ImGui::SetNextWindowSize(viewport->WorkSize);
            ImGui::SetNextWindowViewport(viewport->ID);
            ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0.0f);
            ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 0.0f);
            window_flags |= ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove;
            window_flags |= ImGuiWindowFlags_NoBringToFrontOnFocus | ImGuiWindowFlags_NoNavFocus;
        }
        else
        {
            dockspace_flags &= ~ImGuiDockNodeFlags_PassthruCentralNode;
        }

        // When using ImGuiDockNodeFlags_PassthruCentralNode, DockSpace() will render our background
        // and handle the pass-thru hole, so we ask Begin() to not render a background.
        if (dockspace_flags & ImGuiDockNodeFlags_PassthruCentralNode)
            window_flags |= ImGuiWindowFlags_NoBackground;

        // Important: note that we proceed even if Begin() returns false (aka window is collapsed).
        // This is because we want to keep our DockSpace() active. If a DockSpace() is inactive,
        // all active windows docked into it will lose their parent and become undocked.
        // We cannot preserve the docking relationship between an active window and an inactive docking, otherwise
        // any change of dockspace/settings would lead to windows being stuck in limbo and never being visible.
        if (!opt_padding)
            ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(0.0f, 0.0f));
        ImGui::Begin("DockSpace Demo", nullptr, window_flags);
        if (!opt_padding)
            ImGui::PopStyleVar();

        if (opt_fullscreen)
            ImGui::PopStyleVar(2);

        // Submit the DockSpace
        ImGuiIO& io = ImGui::GetIO();
        if (io.ConfigFlags & ImGuiConfigFlags_DockingEnable)
        {
            ImGuiID dockspace_id = ImGui::GetID("MyDockSpace");
            ImGui::DockSpace(dockspace_id, ImVec2(0.0f, 0.0f), dockspace_flags);
        }
        
		
		ShowMenuBar();
		

        ImGui::End();
    }


	void  MyApplication::ShowMenuBar()
	{
		
		if (ImGui::BeginMenuBar()) {
			if (ImGui::BeginMenu(" 关于 ")) {
				if (ImGui::MenuItem("项目地址")) {
					toLoad = true;
				}

				ImGui::EndMenu();

			}
			ImGui::EndMenuBar();
		}


		if (toLoad)
		{
			ImGui::OpenPopup("提示");
			toLoad = ShowMessage("嘻嘻");
		}
	}

	void  MyApplication::ShowImguiExample()
	{
		static float f = 0.0f;
		static int counter = 0;
		static bool show_demo_window = true;
		static bool show_another_window = true;
		static ImVec4 clear_color = ImVec4(0, 0, 0, 0);

		ImGui::Begin("Example");                          // Create a window called "Hello, world!" and append into it.



		
		ImGui::Text("This is some useful text.");               // Display some text (you can use a format strings too)
		ImGui::Checkbox("Demo Window", &show_demo_window);      // Edit bools storing our window open/close state
		ImGui::Checkbox("Another Window", &show_another_window);

		ImGui::SliderFloat("float", &f, 0.0f, 1.0f);            // Edit 1 float using a slider from 0.0f to 1.0f
		ImGui::ColorEdit3("clear color", (float*)&clear_color); // Edit 3 floats representing a color

		if (ImGui::Button("Button"))                            // Buttons return true when clicked (most widgets return true when edited/activated)
			counter++;
		ImGui::SameLine();
		ImGui::Text("counter = %d", counter);
		
		ImGui::End();
	}

	bool  MyApplication::ShowMessage(const char* message)
	{
		
		// Always center this window when appearing
		ImVec2 center = ImGui::GetMainViewport()->GetCenter();
		ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));

		if (ImGui::BeginPopupModal("提示", NULL, ImGuiWindowFlags_AlwaysAutoResize))
		{


			ImGui::Text(message);

			ImGui::Separator();


			if (ImGui::Button("关闭", ImVec2(120, 0)))
			{

				ImGui::CloseCurrentPopup();
				ImGui::EndPopup();
				return false;

			}
			ImGui::EndPopup();
		}
		return true;
	}
	

			

	

	bool MyApplication::ConnectSW()
	{
		CoInitialize(NULL); //初始化COM库（让Windows加载DLLs）
		if (swApp.CoCreateInstance(__uuidof(SldWorks), NULL, CLSCTX_LOCAL_SERVER) != S_OK)//创建swApp指针的对象实例
		{
			// Stop COM 
			CoUninitialize();
			return false;
		}
		return true;
	}

	bool MyApplication::OpenFile()
	{
		// Open Selected file             
		CComBSTR fileName = "D:/Files/test.SLDPRT";
		long error = NOERROR;
		long warning = NOERROR;

		result = swApp->OpenDoc6(fileName, (int)swDocumentTypes_e::swDocPART, (int)swOpenDocOptions_e::swOpenDocOptions_Silent, nullptr, &error, &warning, &swDoc);//error=2表示无法找到文件

		if (result != S_OK)
		{
			// COM Style String for message to user
			//_messageToUser = (L"Failed to open document.\nPlease try again.");
			//
			//// Send a message to user and store the return value in _lMessageResult by referencing it
			//swApp->SendMsgToUser2(_messageToUser, swMessageBoxIcon_e::swMbInformation, swMessageBoxBtn_e::swMbOk, &_lMessageResult);
			//
			//// Visible the Solidworks
			//swApp->put_Visible(VARIANT_TRUE);

			// Stop COM 
			CoUninitialize();
			return false;
		}
		swApp->put_Visible(VARIANT_TRUE);
		return true;
	}

	bool MyApplication::ReadProperty()
	{
		CComBSTR customFieldNames[2] = { "Description" ,"Weight" };
		for (CComBSTR fieldName : customFieldNames) {
			CComBSTR fieldResult;
			result = swDoc->get_CustomInfo(fieldName, &fieldResult);
			if (result != S_OK) {
				hasProperty = false;
				CoUninitialize();
				return false;
			}

			std::string aaa = GbkToUtf8(_com_util::ConvertBSTRToString(fieldName));

			std::string bbb = GbkToUtf8(_com_util::ConvertBSTRToString(fieldResult));
			property[aaa] = bbb;

		}

		std::unordered_map<swSummInfoField_e, std::string> summaryFieldNames = {
			 {swSummInfoField_e::swSumInfoAuthor,"Author:"}
			,{swSummInfoField_e::swSumInfoComment,"Comment:"}
			,{swSummInfoField_e::swSumInfoCreateDate,"CreateDate:"}
			,{swSummInfoField_e::swSumInfoCreateDate2,"CreateDate2:"}
			,{swSummInfoField_e::swSumInfoKeywords,"Keywords:"}
			,{swSummInfoField_e::swSumInfoSaveDate,"SaveDate:"}
			,{swSummInfoField_e::swSumInfoSaveDate2,"SaveDate2:"}
			,{swSummInfoField_e::swSumInfoSavedBy,"SavedBy:"}
			,{swSummInfoField_e::swSumInfoSubject,"Subject:"}
			,{swSummInfoField_e::swSumInfoTitle,"Title:" }
		};
		for (auto fieldName : summaryFieldNames) {
			CComBSTR fieldResult;
			result = swDoc->get_SummaryInfo(fieldName.first, &fieldResult);
			if (result != S_OK) {
				hasProperty = false;
				CoUninitialize();
				return false;
			}

			std::string bbb = GbkToUtf8(_com_util::ConvertBSTRToString(fieldResult));
			summary[fieldName.second] = bbb;
		}

		hasProperty = true;
		return true;



		//result = swDoc->get_ISelectionManager(&swSelectionManager);

		//long index;
		//long mark;
		//swSelectionManager->GetSelectedObject6(1, -1, &swDispatch);


		//swDispatch = swApp;

		//swDimXpert->get_DimXpertPart();

		//swAnnotation->GetDimXpertFeature();
		//swAnnotation->GetDimXpertName();
		//swAnnotation->IsDimXpert();

		//IDimXpertAnnotation
		//(IDimXpertFeature)swDis
		//DimXpertFeature

	}

	//bool MyApplication::SWBotton(const char* BottonName, SWState state, bool(*func)())
	//{
	//	if (ImGui::Button(BottonName)) {
	//		if (SWStateMap[state] != MyState::Succeed) {
	//			myState = func? MyState::Succeed : MyState::Failed;
	//			SWStateMap[state] = myState;
	//		}
	//		else {
	//			myState = MyState::Nothing;
	//			SWStateMap[state] = myState;
	//		}
	//		ImGui::OpenPopup("提示");
	//	}
	//}

	std::string  MyApplication::GbkToUtf8(const char* src_str)
	{
		int len = MultiByteToWideChar(CP_ACP, 0, src_str, -1, NULL, 0);
		wchar_t* wstr = new wchar_t[len + 1];
		memset(wstr, 0, len + 1);
		MultiByteToWideChar(CP_ACP, 0, src_str, -1, wstr, len);
		len = WideCharToMultiByte(CP_UTF8, 0, wstr, -1, NULL, 0, NULL, NULL);
		char* str = new char[len + 1];
		memset(str, 0, len + 1);
		WideCharToMultiByte(CP_UTF8, 0, wstr, -1, str, len, NULL, NULL);
		std::string strTemp = str;
		if (wstr) delete[] wstr;
		if (str) delete[] str;
		return strTemp;
	}


}

