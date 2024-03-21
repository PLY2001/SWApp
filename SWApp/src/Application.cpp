#include "Application.h"
#include "imgui.h"




namespace MyApp {

	//必须使用CComPtr来定义智能指针，从而简化COM指针的操作，比如自动计数
	CComPtr<ISldWorks> swApp;// COM Pointer of Soldiworks object
	CComPtr<IModelDoc2> swDoc;// COM Pointer of Soldiworks Model Document
	CComPtr<IDispatch> swDispatch;//所有接口的父类(等效于C#的object)
	CComPtr<IConfiguration> swConfiguration;//用于获取DimXpertManager
	CComPtr<IDimXpertManager> swDimXpertManager;//管理DimXpert的一切数据
	CComPtr<IDimXpertPart> swDimXpertPart;//DimXpert零件
	CComPtr<IDimXpertFeature> swDimXpertFeature;//DimXpert特征
	CComPtr<IDimXpertAnnotation> swDimXpertAnnotation;//DimXpert标注
	VARIANT dimXpertAnnotationVT;//获取DimXpert标注的SAFEARRAY数组的载体


	CComPtr<IFace2> swFace;//面
	VARIANT faceVT;//获取面的SAFEARRAY数组的载体
	VARIANT boxVT;//获取面的包围盒的SAFEARRAY数组的载体	
	CComPtr<IMathUtility> swMathUtility;//用于生成数学向量、矩阵等
	CComPtr<IMathPoint> startPoint;//投影光线起点，单位m
	CComPtr<IMathVector> projectDir;//投影光线方向
	CComPtr<IMathPoint> interactPoint;//投影光线与面的交点
	VARIANT startPointVT;//用于生成投影光线起点的SAFEARRAY数组的载体
	VARIANT projectDirVT;//用于生成投影光线方向的SAFEARRAY数组的载体
	VARIANT interactPointVT;//用于生成投影光线与面的交点的SAFEARRAY数组的载体

	HRESULT result = NOERROR; //存储函数的输出结果
	
	//CComBSTR _messageToUser;// COM Style String for message to user
	//long _lMessageResult;// long type variable to store the result value by user

	void MyApplication::ShowMyApp()
    {
		EnableDocking(); //开启Docking特性
		//ShowImguiExample();
		//ImGui::ShowDemoWindow();

        ImGui::Begin("SolidWorks API");
        ImGui::Text("%.3f ms/frame (%.1f FPS)", 1000.0f / ImGui::GetIO().Framerate, ImGui::GetIO().Framerate);
		
		//连接SW按钮
		if (ImGui::Button("连接SW")) {			
			myState = ConnectSW() ? MyState::Succeed : MyState::Failed;
			SWStateMap[SWState::Connected] = myState;
			ImGui::OpenPopup("提示");
		}
		ImGui::SameLine();
		ImGui::Text(MyStateMessage[(int)SWStateMap[SWState::Connected]].c_str());

		//打开文件按钮
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

		//读取属性按钮
		if (ImGui::Button("读取属性")) {
			if (SWStateMap[SWState::Connected] == MyState::Succeed && SWStateMap[SWState::FileOpen] == MyState::Succeed) {
				myState = ReadProperty() ? MyState::Succeed : MyState::Failed;
				hasProperty = myState == MyState::Succeed ? true : false;
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

		//读取MBD特征及其标注按钮
		if (ImGui::Button("读取MBD特征及其标注")) {
			if (SWStateMap[SWState::Connected] == MyState::Succeed && SWStateMap[SWState::FileOpen] == MyState::Succeed) {
				myState = ReadMBD() ? MyState::Succeed : MyState::Failed;
				hasMBD = myState == MyState::Succeed ? true : false;
				SWStateMap[SWState::MBDGot] = myState;
			}
			else
			{
				myState = MyState::Nothing;
				SWStateMap[SWState::MBDGot] = myState;
			}
			ImGui::OpenPopup("提示");
		}
		ImGui::SameLine();
		ImGui::Text(MyStateMessage[(int)SWStateMap[SWState::MBDGot]].c_str());

		//显示弹窗
		ShowMessage(MyStateMessage[(int)myState].c_str());
		
		//显示属性
		if (hasProperty) {
			if (ImGui::CollapsingHeader("属性")) {
				if (ImGui::TreeNode("自定义属性")){
					for (auto p : property) {
						std::string m = p.first + ":";
						m = m + p.second;
						ImGui::Text(m.c_str());
					}
					ImGui::TreePop();
					ImGui::Separator();
				}
				if (ImGui::TreeNode("摘要")) {
					for (auto s : summary) {
						std::string m = s.first + s.second;
						ImGui::Text(m.c_str());
					}
					ImGui::TreePop();
					ImGui::Separator();
				}
			}
		}

		//显示MBD
		if (hasMBD) {
			if (ImGui::CollapsingHeader("MBD特征及其标注")){					
				ImGui::Text("MBD特征总数:%d", DimXpertFeatureCount);
				ImGui::Text("MBD标注总数:%d", DimXpertAnnotationCount);
				ImGui::Separator();
				for (auto d : DimXpertMap) {
					if (ImGui::TreeNode(d.first.c_str())) {
						for (auto a : d.second) {
							ImGui::Text(a.c_str());
						}
						ImGui::TreePop();
						ImGui::Separator();
					}

				}
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
			toLoad = ShowMessage("github.com/PLY2001/SWApp");
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
		swApp.Release();//Realease的作用是避免重复初始化swApp，导致出错
		if (swApp.CoCreateInstance(__uuidof(SldWorks), NULL, CLSCTX_LOCAL_SERVER) != S_OK)//创建swApp指针的对象实例
		{
			// Stop COM 
			CoUninitialize();
			return false;
		}
		swMathUtility.Release();
		result = swApp->IGetMathUtility(&swMathUtility);//由swApp初始化swMathUtility
		if (result != S_OK) {
			CoUninitialize();
			return false;
		}
		return true;
	}

	bool MyApplication::OpenFile()
	{
		// Open Selected file             
		CComBSTR fileName = "D:/Projects/SWApp/SolidWorks Part/base.SLDPRT";
		long error = NOERROR;
		long warning = NOERROR;

		//打开文件
		swDoc.Release();
		result = swApp->OpenDoc6(fileName, (int)swDocumentTypes_e::swDocPART, (int)swOpenDocOptions_e::swOpenDocOptions_Silent, nullptr, &error, &warning, &swDoc);//error=2表示无法找到文件

		if (result!=S_OK || error != NOERROR)
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
		CComBSTR customFieldNames[2] = { "Description" ,"Weight" };//设置需读取的自定义属性
		for (CComBSTR fieldName : customFieldNames) {
			CComBSTR fieldResult;
			result = swDoc->get_CustomInfo(fieldName, &fieldResult);
			if (result != S_OK) {
				CoUninitialize();
				return false;
			}
			std::string aaa = GbkToUtf8(_com_util::ConvertBSTRToString(fieldName));
			std::string bbb = GbkToUtf8(_com_util::ConvertBSTRToString(fieldResult));
			property[aaa] = bbb;
		}

		//设置需读取的摘要
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
				CoUninitialize();
				return false;
			}
			std::string bbb = GbkToUtf8(_com_util::ConvertBSTRToString(fieldResult));
			summary[fieldName.second] = bbb;
		}

		return true;

		

	}

	bool MyApplication::ReadMBD()
	{
		//swDoc->swConfiguration->swDimXpertManager->swDimXpertPart->Annotation和Feature
		swConfiguration.Release();
		result = swDoc->IGetActiveConfiguration(&swConfiguration);//获取swConfiguration
		if (result != S_OK) {
			CoUninitialize();
			return false;
		}
		swDimXpertManager.Release();
		result = swConfiguration->get_DimXpertManager(VARIANT_TRUE, &swDimXpertManager);//获取swDimXpertManager
		if (result != S_OK) {
			CoUninitialize();			
			return false;
		}
		swDispatch.Release();
		result = swDimXpertManager->get_DimXpertPart(&swDispatch);//获取swDimXpertPart(由swDispatch父类接口实例承载)
		if (result != S_OK) {
			CoUninitialize();			
			return false;
		}
		swDimXpertPart = swDispatch;//转化为具体接口类型
		result = swDimXpertPart->GetFeatureCount(&DimXpertFeatureCount);//获取特征数量
		if (result != S_OK) {
			CoUninitialize();
			return false;
		}
		result = swDimXpertPart->GetAnnotationCount(&DimXpertAnnotationCount);//读取标注数量
		if (result != S_OK) {
			CoUninitialize();			
			return false;
		}
		swDimXpertPart->GetAnnotations(&dimXpertAnnotationVT);//获取标注SAFEARRAY数组的承载体
		if (result != S_OK) {
			CoUninitialize();			
			return false;
		}
		
		//读取DimXpert标注的SAFEARRAY
		LPVOID aData = nullptr;//接收读取后的数组
		LONG itemCount;//接收读取后的数组大小
		if (!ReadSafeArray(&dimXpertAnnotationVT, VT_DISPATCH, 1, &aData, &itemCount)) {
			CoUninitialize();
			return false;
		}
		// here you can cast pData to an array (pointer) of the type you expect
		IDispatch** myaData = (IDispatch**)aData;///////////////////////////////////将数组指针赋与IDispatch**类型的指针数组的指针
		// use the data here.
		IDimXpertAnnotation* myAnnotationData;//用于获取IDimXpertAnnotation*类型数据						
		CComBSTR dimXpertFeatureName;
		CComBSTR dimXpertAnnotationName;
		std::string dimXpertFeatureNameStr;
		std::string dimXpertAnnotationNameStr;
		for (int i = 0; i < itemCount; i++) {
			result = myaData[i]->QueryInterface(IID_IDimXpertAnnotation, (void**)&myAnnotationData);//为了将IDispatch*类型转为IDimXpertAnnotation*，需要用QueryInterface查询是否可转换(CComPtr类型直接=即可)，IID_IDimXpertAnnotation是要查询的接口类型
			if (result != S_OK) {
				CoUninitialize();										
				return false;
			}
			
			swDimXpertAnnotation = CComPtr<IDimXpertAnnotation>(myAnnotationData);//用构造函数将IDimXpertAnnotation*普通指针转为CComPtr智能指针
			swDimXpertFeature.Release();//不Release的话，get_Feature(&swDimXpertFeature);会报错
			result = swDimXpertAnnotation->get_Feature(&swDimXpertFeature);
			if (result != S_OK) {
				CoUninitialize();										
				return false;
			}
			result = swDimXpertFeature->get_Name(&dimXpertFeatureName);//result为false？不知为何，但是能读取
			//if (result != S_OK) {
			//	CoUninitialize();										
			//	return false;
			//}
			result = swDimXpertAnnotation->get_Name(&dimXpertAnnotationName);
			//if (result != S_OK) {
			//	CoUninitialize();										
			//	return false;
			//}
			
			dimXpertFeatureNameStr = GbkToUtf8(_com_util::ConvertBSTRToString(dimXpertFeatureName));
			dimXpertAnnotationNameStr = GbkToUtf8(_com_util::ConvertBSTRToString(dimXpertAnnotationName));
			DimXpertMap[dimXpertFeatureNameStr].push_back(dimXpertAnnotationNameStr);
			
			//读取DimXpert特征所对应的面
			result = swDimXpertFeature->GetFaces(&faceVT);
			//读取面的SAFEARRAY
			LPVOID fData = nullptr;
			LONG faceCount;
			if (!ReadSafeArray(&faceVT, VT_DISPATCH, 1, &fData, &faceCount)) {
				CoUninitialize();
				return false;
			}
			// here you can cast pData to an array (pointer) of the type you expect
			IDispatch** myfData = (IDispatch**)fData;
			// use the data here.
			IFace2* myFaceData;//用于获取IFace2*类型数据						
			for (int i = 0; i < faceCount; i++) {
				result = myfData[i]->QueryInterface(IID_IFace2, (void**)&myFaceData);
				if (result != S_OK) {
					CoUninitialize();
					return false;
				}

				swFace = CComPtr<IFace2>(myFaceData);
				
				myFaceData->GetBox(&boxVT);//获取包围盒坐标。一共6个值：第一个点的xyz，第二个点的xyz，单位m
				//读取包围盒的SAFEARRAY
				LPVOID bData = nullptr;
				LONG boxCount;
				if (!ReadSafeArray(&boxVT, VT_R8, 1, &bData, &boxCount)) {
					CoUninitialize();
					return false;
				}
				// here you can cast pData to an array (pointer) of the type you expect
				double* mybData = (double*)bData;
				// use the data here.
				double myBoxPos1[3] = { 0,0,0 };//用于获取double类型数据	
				double myBoxPos2[3] = { 0,0,0 };//用于获取double类型数据	
				for (int i = 0; i < boxCount; i++) {
					if (i < 3)
						myBoxPos1[i] = mybData[i];//包围盒点1
					else
						myBoxPos2[i - 3] = mybData[i];//包围盒点2
				}

				double thisPos[3];//目前的投影光线起点
				double dir[3] = { 1,0,0 };//目前的投影光线方向
				int sampleCount = 10;//投影采样次数
				for (int i = 0; i < sampleCount; i++) {
					thisPos[0] = myBoxPos1[0] + i * (myBoxPos2[0] - myBoxPos1[0]) / sampleCount;
					thisPos[1] = myBoxPos1[1] + i * (myBoxPos2[1] - myBoxPos1[1]) / sampleCount;
					thisPos[2] = myBoxPos1[2] + i * (myBoxPos2[2] - myBoxPos1[2]) / sampleCount;

					startPoint.Release();
					projectDir.Release();
					interactPoint.Release();

					CreatVARIANTArray(3, VT_R8, thisPos, &startPointVT);//生成VARIANT数组
					swDispatch.Release();
					result = swMathUtility->CreatePoint(startPointVT, &swDispatch);//生成点
					startPoint = swDispatch;

					CreatVARIANTArray(3, VT_R8, dir, &projectDirVT);//生成VARIANT数组
					swDispatch.Release();
					result = swMathUtility->CreateVector(projectDirVT, &swDispatch);//生成向量
					projectDir = swDispatch;

					result = swFace->GetProjectedPointOn(startPoint, projectDir, &interactPoint);//投影，求得的交点单位是m，若未相交为NULL
					if (interactPoint != NULL) {
						result = interactPoint->get_ArrayData(&interactPointVT);
						LPVOID iData = nullptr;
						LONG iCount;
						if (ReadSafeArray(&interactPointVT, VT_R8, 1, &iData, &iCount)) {
							//存数据
						}

					}

				}


				
				
				
				
			}
			
			
			
		}
		
		


		//获取建模的特征（非DimXpert）
		//result = swDoc->get_FeatureManager(&swFeatureManager);
		//if (result != S_OK) {
		//	CoUninitialize();
		//	return false;
		//}
		//result = swFeatureManager->get_FeatureStatistics(&swFeatureStatistics);
		//if (result != S_OK) {
		//	CoUninitialize();
		//	return false;
		//}
		//VARIANT_BOOL temp1 = VARIANT_FALSE;
		//swFeatureStatistics->Refresh(&temp1);
		//
		//result = swFeatureStatistics->get_FeatureCount(&featureCount);
		//if (result != S_OK) {
		//	CoUninitialize();
		//	return false;
		//}
		//result = swFeatureStatistics->get_FeatureNames(&featureNames);
		//// verify that it's an array
		//if (V_ISARRAY(&featureNames))
		//{
		//	// get safe array
		//	LPSAFEARRAY pSafeArray = V_ARRAY(&featureNames);
		//
		//	// determine the type of item in the array
		//	VARTYPE itemType;
		//	if (SUCCEEDED(SafeArrayGetVartype(pSafeArray, &itemType)))
		//	{
		//		// verify it's the type you expect
		//		// (The API you're using probably returns a safearray of VARIANTs,
		//		// so I'll use VT_VARIANT here. You should double-check this.)
		//		if (itemType == VT_BSTR)//////////////////////////////////////////////////////////////////////
		//		{
		//			// verify that it's a one-dimensional array
		//			// (The API you're using probably returns a one-dimensional array.)
		//			if (SafeArrayGetDim(pSafeArray) == 1)
		//			{
		//				// determine the upper and lower bounds of the first dimension
		//				LONG lBound;
		//				LONG uBound;
		//				if (SUCCEEDED(SafeArrayGetLBound(pSafeArray, 1, &lBound)) && SUCCEEDED(SafeArrayGetUBound(pSafeArray, 1, &uBound)))
		//				{
		//					// determine the number of items in the array
		//					LONG itemCount = uBound - lBound + 1;
		//
		//					// begin accessing data
		//					LPVOID pData;
		//					if (SUCCEEDED(SafeArrayAccessData(pSafeArray, &pData)))
		//					{
		//						// here you can cast pData to an array (pointer) of the type you expect
		//						// (The API you're using probably returns a safearray of VARIANTs,
		//						// so I'll use VARIANT here. You should double-check this.)
		//						BSTR* sgg = (BSTR*)pData;////////////////////////////////////////////////////////////////////////
		//
		//						// use the data here.
		//						for (int i = 0; i++; i < 8) {
		//							s[i] = GbkToUtf8(_com_util::ConvertBSTRToString(sgg[i]));
		//						}
		//
		//						// end accessing data
		//						SafeArrayUnaccessData(pSafeArray);
		//					}
		//				}
		//			}
		//		}
		//	}
		//}

		

		
		return true;
	}

	

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


	bool MyApplication::ReadSafeArray(VARIANT* vt,VARENUM vtType,int dimensional,LPVOID* pData, LONG* itemCount)
	{
		//读取SAFEARRAY
		// verify that it's an array
		if (V_ISARRAY(vt))
		{
			// get safe array
			SAFEARRAY* pSafeArray = V_ARRAY(vt);
			// determine the type of item in the array
			VARTYPE itemType;
			if (SUCCEEDED(SafeArrayGetVartype(pSafeArray, &itemType)))
			{
				// verify it's the type you expect
				if (itemType == vtType)///////////////////////该数组类型为存储IDispatch*指针的数组
				{
					// verify that it's a one-dimensional array
					if (SafeArrayGetDim(pSafeArray) == dimensional)
					{
						// determine the upper and lower bounds of the first dimension
						LONG lBound;
						LONG uBound;
						if (SUCCEEDED(SafeArrayGetLBound(pSafeArray, 1, &lBound)) && SUCCEEDED(SafeArrayGetUBound(pSafeArray, 1, &uBound)))
						{
							// determine the number of items in the array
							*itemCount = uBound - lBound + 1;
							// begin accessing data
							//LPVOID pData;
							if (SUCCEEDED(SafeArrayAccessData(pSafeArray, &*pData)))//提取数组指针至pData
							{
								
								// end accessing data
								SafeArrayUnaccessData(pSafeArray);
								return true;
							}
							else {
								CoUninitialize();
								return false;
							}
						}
						else {
							CoUninitialize();
							return false;
						}
					}
				}
			}
			else {
				CoUninitialize();
				return false;
			}
		}
	}

	template<typename T>
	bool MyApplication::CreatVARIANTArray(int size, VARENUM type, T* buffer, VARIANT* array)
	{
		SAFEARRAY* psa; //使用数组整理读取的数据
		SAFEARRAYBOUND rgsabound[1];
		rgsabound[0].cElements = size; //设置数组的大小
		rgsabound[0].lLbound = 0;
		psa = SafeArrayCreate(type, 1, rgsabound); //创建SafeArray数组

		long len = psa->rgsabound[0].cElements;
		for (long i = 0; i < len; i++) {
			result = SafeArrayPutElement(psa, &i, &buffer[i]);
			if (result != S_OK) {
				CoUninitialize();
				return false;
			}
		}
		array->vt = VT_ARRAY | VT_R8; //数组类型
		array->parray = psa;
		return true;
	}

}

